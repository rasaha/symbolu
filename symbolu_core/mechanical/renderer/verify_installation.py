#!/usr/bin/env python3
"""
Fusion Renderer v3.0 - Verification Script
===========================================

Quick verification that the module is installed and working correctly.

Run with: python verify_installation.py
"""

import sys
from datetime import datetime


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(text)
    print("="*70)


def verify_import():
    """Verify module can be imported"""
    print_header("1. Verifying Import")
    try:
        from fusion_renderer import (
            FusionRenderer,
            FusionOutput,
            RenderMode,
            Domain,
            render_fusion_output
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def verify_basic_functionality():
    """Verify basic rendering works"""
    print_header("2. Verifying Basic Functionality")
    try:
        from fusion_renderer import FusionRenderer, FusionOutput
        
        # Create test input
        fusion_output = FusionOutput(
            query="Test query",
            merged_response="Test response",
            hrm_content={"reasoning": "Test reasoning"},
            lcm_content={"content": "Test content"},
            moe_content={"content": "Test expertise"},
            channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
            conflict_resolution=[],
            metadata={}
        )
        
        # Render
        renderer = FusionRenderer()
        output = renderer.render(fusion_output)
        
        print("✅ Basic rendering successful")
        print(f"   Query: {output.query}")
        print(f"   Mode: {output.mode}")
        print(f"   Layers: Symbolic={'Yes' if output.symbolic_layer else 'No'}, "
              f"Practical={'Yes' if output.practical_layer else 'No'}, "
              f"Mirror={'Yes' if output.mirror_truth_layer else 'No'}")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_modes():
    """Verify all modes work"""
    print_header("3. Verifying Operating Modes")
    try:
        from fusion_renderer import FusionRenderer, FusionOutput, RenderMode
        
        fusion_output = FusionOutput(
            query="Test",
            merged_response="Test",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
            conflict_resolution=[],
            metadata={}
        )
        
        modes = [RenderMode.MINIMAL, RenderMode.STANDARD, 
                RenderMode.SYMBOLIC, RenderMode.REGULATED]
        
        for mode in modes:
            renderer = FusionRenderer(mode=mode)
            output = renderer.render(fusion_output)
            print(f"✅ {mode.value.upper()} mode working")
        
        return True
        
    except Exception as e:
        print(f"❌ Mode verification failed: {e}")
        return False


def verify_determinism():
    """Verify deterministic behavior"""
    print_header("4. Verifying Determinism")
    try:
        from fusion_renderer import FusionRenderer, FusionOutput
        
        fusion_output = FusionOutput(
            query="Determinism test",
            merged_response="Test response",
            hrm_content={"reasoning": "Test"},
            lcm_content={"content": "Test"},
            moe_content={"content": "Test"},
            channel_weights={"hrm": 0.5, "lcm": 0.3, "moe": 0.2},
            conflict_resolution=[],
            metadata={}
        )
        
        renderer = FusionRenderer()
        
        # Render twice
        output1 = renderer.render(fusion_output)
        output2 = renderer.render(fusion_output)
        
        # Check determinism (excluding timestamp which is expected to differ)
        import json
        dict1 = json.loads(output1.to_json())
        dict2 = json.loads(output2.to_json())
        
        # Remove timestamps for comparison
        dict1.pop('render_timestamp', None)
        dict2.pop('render_timestamp', None)
        
        if json.dumps(dict1, sort_keys=True) == json.dumps(dict2, sort_keys=True):
            print("✅ Deterministic behavior verified")
            print("   Same input produces identical output (excluding timestamps)")
            return True
        else:
            print("❌ Non-deterministic behavior detected")
            return False
            
    except Exception as e:
        print(f"❌ Determinism verification failed: {e}")
        return False


def verify_json_output():
    """Verify JSON serialization"""
    print_header("5. Verifying JSON Serialization")
    try:
        from fusion_renderer import FusionRenderer, FusionOutput
        import json
        
        fusion_output = FusionOutput(
            query="JSON test",
            merged_response="Test",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
            conflict_resolution=[],
            metadata={}
        )
        
        renderer = FusionRenderer()
        output = renderer.render(fusion_output)
        
        # Test JSON serialization
        json_str = output.to_json()
        parsed = json.loads(json_str)
        
        print("✅ JSON serialization working")
        print(f"   JSON size: {len(json_str)} bytes")
        return True
        
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False


def verify_statistics():
    """Verify statistics tracking"""
    print_header("6. Verifying Statistics")
    try:
        from fusion_renderer import FusionRenderer, FusionOutput
        
        renderer = FusionRenderer()
        
        # Process multiple requests
        for i in range(5):
            fusion_output = FusionOutput(
                query=f"Test {i}",
                merged_response="Test",
                hrm_content={},
                lcm_content={},
                moe_content={},
                channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
                conflict_resolution=[],
                metadata={}
            )
            renderer.render(fusion_output)
        
        stats = renderer.get_stats()
        
        print("✅ Statistics tracking working")
        print(f"   Total renders: {stats['total_renders']}")
        print(f"   Avg render time: {stats['avg_render_time_ms']:.2f} ms")
        return True
        
    except Exception as e:
        print(f"❌ Statistics verification failed: {e}")
        return False


def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("FUSION RENDERER v3.0 - INSTALLATION VERIFICATION")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run all verifications
    results.append(("Import", verify_import()))
    results.append(("Basic Functionality", verify_basic_functionality()))
    results.append(("Operating Modes", verify_modes()))
    results.append(("Determinism", verify_determinism()))
    results.append(("JSON Serialization", verify_json_output()))
    results.append(("Statistics", verify_statistics()))
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All verifications passed! Module is ready to use.")
        return 0
    else:
        print("\n⚠️  Some verifications failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
