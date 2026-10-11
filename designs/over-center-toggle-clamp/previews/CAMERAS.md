# Frozen preview shots — over-center-toggle-clamp

Rendered by `./scripts/render.sh over-center-toggle-clamp --previews`
from `cameras.conf`. Cameras are **frozen** once reviewed — a new region gets
a new line, never a moved camera.

| Shot | What the reviewer checks in it |
|---|---|
| `contact-sheet` | iso / top / front / bottom-iso of the whole print: overhangs, bed contact, that nothing floats |
| `iso-open` | Hero: the whole clamp at the printed (open) pose — jaws, lever, arch |
| `top-open` | Plan view: jaw gap at open (25 mm), rail/lip capture, M5 mounts at 40 mm centres, lever tail over the arch |
| `mechanism` | Side elevation: the Z stack (plate / rails / carrier / lever / link), the arch beam and its posts, pin heads |
| `cam-closeup` | The cam flank / nub engagement zone and the handle paddle at the printed pose |
| `coupon` | The force-measuring artifact — the same production arch between anchored posts with the pull tab |
| `coupon-wide` | The whole coupon in one wide frame — both posts, the full arch span, and the tab standing at the apex with the pull hole through its tip |
| `workpiece-held` | The clamp clamping: the lever seated past dead center into its closed stop, a 1.6 mm PCB-class plate (colored — the preview-only `workpiece-held` pose, never printed) gripped between the jaws |
| `under-lever` | The skeptic's view: ~15° elevation looking under the open lever band — the sacrificial film shelves beneath the paddle and crank, and daylight between every moving part and the plate |
