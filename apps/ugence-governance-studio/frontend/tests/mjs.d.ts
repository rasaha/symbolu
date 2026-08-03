// The Node verifier scripts (.mjs) are plain JS with no type declarations. They
// are unit-tested from TypeScript; declare them as untyped modules so the strict
// TS program can import them. (Their behavior is asserted by the tests.)
declare module "*.mjs";
