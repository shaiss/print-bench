// Print-this-first fit coupon for the NUGGS turnaround node. Include-and-
// override on the production entry point — no copied geometry; the port is
// the library's own nuggs_neck stub, the same shape every NUGGS module tunes
// port_tol on. The wrapper relies on include-then-override semantics: the
// override stays above nothing (there is no geometry above it in this file),
// and the entry point dispatches on `part`.
include <nuggs-turnaround.scad>
part = "coupon";
