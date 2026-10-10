// Print-this-first fit coupon for the NUGGS bottle adapter. Include-and-
// override on the production entry point — no copied geometry: the port
// station is the library's own nuggs_neck stub, the throat stations are the
// production throat_cavity on plain rings. The wrapper relies on
// include-then-override semantics: the override stays above any geometry
// (there is none above it here), and the entry point dispatches on `part`.
include <nuggs-bottle-adapter.scad>
part = "coupon";
