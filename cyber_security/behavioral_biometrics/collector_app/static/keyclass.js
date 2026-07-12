// Privacy-safe key CLASS mapping — mirrors privacy.key_to_class (Python) exactly.
// The raw key (event.key) is passed in only to derive the class and is NEVER stored
// or transmitted. Parity with the Python implementation is asserted by
// tests/test_keyclass_parity via node.
(function (root) {
  var PUNCT = "`~!@#$%^&*()-_=+[]{}\\|;:'\",.<>/?";
  var NAV = ["arrowleft", "arrowright", "arrowup", "arrowdown", "home", "end", "pageup", "pagedown"];
  var MOD = ["shift", "control", "ctrl", "alt", "meta", "capslock", "cmd", "option", "fn"];

  function isFunc(lk) { return /^f([1-9]|1[0-9]|2[0-4])$/.test(lk); }

  function keyToClass(key) {
    if (key === null || key === undefined) return "other";
    var k = String(key);
    if (/^[A-Za-z]$/.test(k)) return "letter";
    if (/^[0-9]$/.test(k)) return "digit";
    var lk = k.toLowerCase();
    if (k === " " || lk === "space" || lk === "spacebar") return "space";
    if (lk === "backspace" || lk === "delete" || lk === "del") return "backspace";
    if (lk === "enter" || lk === "return") return "enter";
    if (lk === "tab") return "tab";
    if (NAV.indexOf(lk) >= 0) return "navigation";
    if (MOD.indexOf(lk) >= 0) return "modifier";
    if (isFunc(lk)) return "function";
    if (k.length === 1 && PUNCT.indexOf(k) >= 0) return "punctuation";
    return "other";
  }

  // content-free per-session key id: class + salted hash bucket (no character).
  // Uses a tiny non-crypto hash purely to preserve digraph STRUCTURE within a session.
  function safeKeyId(key, salt) {
    var cls = keyToClass(key);
    if (cls !== "letter" && cls !== "digit" && cls !== "punctuation") return "k:" + cls;
    var s = salt + "|" + String(key), h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
    return "k:" + cls + ":" + ("00000000" + h.toString(16)).slice(-8);
  }

  var api = { keyToClass: keyToClass, safeKeyId: safeKeyId };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.KeyClass = api;
})(typeof window !== "undefined" ? window : globalThis);
