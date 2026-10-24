// Print-this-first coupon (see NOTES.md): a 6-pocket strip of the production
// rail sweeping the hex fit — two pockets each of -0.15 / 0 / +0.15 across
// flats, values embossed on the front wall. Drop bits in, feel which grips
// and still releases one-handed, then print the rail at the winner
// (`-D 'hex_fit=<v>'`). Nothing here is copied geometry: production
// modules, production pocket depth. The pitch is widened 16 -> 24 only to
// give the embossed fit labels room — a stroke >= 0.8 mm (printcheck's
// thin-wall floor) makes each "-0.15" label ~22 mm wide, which the
// production pitch's 16 mm cannot hold; the pitch carries no fit, so the
// sweep is unaffected.
include <hex-bit-rail.scad>
part = "rail-short";
pockets = 6;
pitch = 24;
rail_w = 18;
pocket_fits = [-0.15, -0.15, 0, 0, 0.15, 0.15];
pocket_labels = true;
