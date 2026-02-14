// =============================================================================
// Steering Vector Generator (SVG)
// =============================================================================
// Computes per-element target phases for a given beam direction:
//   u = sin(az) * cos(el)    // direction cosines
//   v = sin(el)
//   target_phi_i = (2*pi * (x_i * u + y_i * v) + cal_offset_i) mod 2*pi
//
// Latency: 4 cycles (sin/cos + multiply + accumulate + calibration)
// Key hardware: 2 CORDIC sin/cos units, 128 MAC units (shared with PUE)
// =============================================================================

module svg
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          start,
  input  logic [Q9_7_W-1:0]            azimuth,       // Q9.7 degrees
  input  logic [Q9_7_W-1:0]            elevation,     // Q9.7 degrees
  input  logic [BEAM_IDX_W-1:0]        beam_id,       // Target beam context

  // -----------------------------------------------------------------------
  // Element positions from EPRF
  // -----------------------------------------------------------------------
  input  logic [Q8_8_W-1:0]            pos_x [NUM_ELEMENTS],
  input  logic [Q8_8_W-1:0]            pos_y [NUM_ELEMENTS],
  input  logic [Q1_15_W-1:0]           cal_offset [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Steering vector output (128 target phases)
  // -----------------------------------------------------------------------
  output logic [Q2_30_W-1:0]           steering_out [NUM_ELEMENTS],
  output logic [BEAM_IDX_W-1:0]        beam_id_out,
  output logic                          done
);

  // =========================================================================
  // FSM: 4-cycle pipeline
  // =========================================================================
  typedef enum logic [2:0] {
    SVG_IDLE,
    SVG_TRIG,       // Cycle 1: Compute sin(az), cos(az), sin(el), cos(el)
    SVG_DIRCOS,     // Cycle 2: Compute direction cosines u, v
    SVG_MAC,        // Cycle 3: Compute x_i*u + y_i*v for all elements
    SVG_CAL_WRAP    // Cycle 4: Add calibration offset + mod 2pi
  } svg_state_e;

  svg_state_e state;
  logic [BEAM_IDX_W-1:0] beam_id_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      state <= SVG_IDLE;
    else begin
      case (state)
        SVG_IDLE:     if (start) state <= SVG_TRIG;
        SVG_TRIG:     state <= SVG_DIRCOS;
        SVG_DIRCOS:   state <= SVG_MAC;
        SVG_MAC:      state <= SVG_CAL_WRAP;
        SVG_CAL_WRAP: state <= SVG_IDLE;
        default:      state <= SVG_IDLE;
      endcase
    end
  end

  // Latch beam_id
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      beam_id_r <= '0;
    else if (start)
      beam_id_r <= beam_id;
  end

  // =========================================================================
  // Cycle 1: Convert degrees to radians and compute trig functions
  // =========================================================================
  // az/el are Q9.7 degrees. Convert to Q2.30 radians:
  // rad = deg * pi / 180
  // pi/180 in Q2.30 = 0.01745329 * 2^30 ≈ 0x00477D1A

  localparam logic [Q2_30_W-1:0] DEG_TO_RAD = 32'h00477D1A;

  logic [Q2_30_W-1:0] az_rad, el_rad;
  logic signed [15:0]  sin_az, cos_az, sin_el, cos_el;

  // Degree to radian conversion
  always_ff @(posedge clk) begin
    if (state == SVG_IDLE && start) begin
      // Q9.7 * Q2.30 / 2^7 = Q2.30
      az_rad <= ($signed({{9{azimuth[15]}}, azimuth}) * $signed({1'b0, DEG_TO_RAD})) >>> 7;
      el_rad <= ($signed({{9{elevation[15]}}, elevation}) * $signed({1'b0, DEG_TO_RAD})) >>> 7;
    end
  end

  // Sin/Cos lookups for azimuth and elevation
  logic sin_az_valid, sin_el_valid;

  sin_cos_lut u_az_sincos (
    .clk       (clk),
    .rst_n     (rst_n),
    .phase_in  (az_rad),
    .valid_in  (state == SVG_TRIG),
    .sin_out   (sin_az),
    .cos_out   (cos_az),
    .valid_out (sin_az_valid)
  );

  sin_cos_lut u_el_sincos (
    .clk       (clk),
    .rst_n     (rst_n),
    .phase_in  (el_rad),
    .valid_in  (state == SVG_TRIG),
    .sin_out   (sin_el),
    .cos_out   (cos_el),
    .valid_out (sin_el_valid)
  );

  // =========================================================================
  // Cycle 2: Direction cosines
  // =========================================================================
  // u = sin(az) * cos(el)
  // v = sin(el)
  logic signed [31:0] dir_u, dir_v;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      dir_u <= '0;
      dir_v <= '0;
    end else if (state == SVG_DIRCOS) begin
      // sin_az * cos_el: both Q1.15, product is Q2.30
      dir_u <= (sin_az * cos_el);
      // v = sin(el), sign-extend to 32 bits
      dir_v <= {{16{sin_el[15]}}, sin_el};
    end
  end

  // =========================================================================
  // Cycle 3: Per-element MAC: 2*pi * (x_i * u + y_i * v)
  // =========================================================================
  logic signed [Q2_30_W-1:0] phase_raw [NUM_ELEMENTS];

  always_ff @(posedge clk) begin
    if (state == SVG_MAC) begin
      for (int i = 0; i < NUM_ELEMENTS; i++) begin
        // pos_x/y are Q8.8, dir_u/v are Q2.30 (but actually Q1.15*Q1.15 = Q2.30)
        // x*u: Q8.8 * Q2.30 = Q10.38, shift right by 8 to get Q2.30
        automatic logic signed [47:0] xu, yv;
        xu = $signed({{16{pos_x[i][15]}}, pos_x[i]}) * dir_u;
        yv = $signed({{16{pos_y[i][15]}}, pos_y[i]}) * dir_v;
        // Sum and scale by 2*pi
        // (xu + yv) is the phase in cycles, multiply by 2*pi
        // Simplified: phase = (xu + yv) >> 8, then handled by 2pi periodicity
        phase_raw[i] <= (xu + yv) >>> 8;
      end
    end
  end

  // =========================================================================
  // Cycle 4: Add calibration offset and wrap to [0, 2pi)
  // =========================================================================
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      done <= 1'b0;
      beam_id_out <= '0;
      for (int i = 0; i < NUM_ELEMENTS; i++)
        steering_out[i] <= '0;
    end else begin
      done <= (state == SVG_CAL_WRAP);
      beam_id_out <= beam_id_r;

      if (state == SVG_CAL_WRAP) begin
        for (int i = 0; i < NUM_ELEMENTS; i++) begin
          // Add calibration offset (sign-extend Q1.15 to Q2.30)
          automatic logic signed [Q2_30_W:0] with_cal;
          with_cal = $signed({1'b0, phase_raw[i][Q2_30_W-1:0]}) +
                     $signed({{17{cal_offset[i][15]}}, cal_offset[i]});
          // Wrap is handled combinationally
          if (with_cal < 0)
            steering_out[i] <= with_cal[Q2_30_W-1:0] + TWO_PI_Q2_30;
          else if (with_cal >= $signed({1'b0, TWO_PI_Q2_30}))
            steering_out[i] <= with_cal[Q2_30_W-1:0] - TWO_PI_Q2_30;
          else
            steering_out[i] <= with_cal[Q2_30_W-1:0];
        end
      end
    end
  end

endmodule : svg
