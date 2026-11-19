# Award logo downloads

Downloaded 2026-11-19. Original files, without cropping, resizing, or redrawing.

| File | Format / dimensions | Source |
| --- | --- | --- |
| `max-planck-medal.avif` | AVIF, 3000 × 3089; photograph of the medal | [University of Twente announcement](https://www.utwente.nl/en/news/2018/11/241237/max-planck-medal-for-detlef-lohse), [image](https://utwente.becdn.net/.wh/ea/uc/i85c3be0d0102e544410065d6ef017ada70f02b0b32810701c3b80b000085/mp-medaille-vs.avif) |
| `canada-gairdner-international-award.svg` | Vector; full Canada Gairdner Awards wordmark | [Gairdner official website](https://www.gairdner.org/), [image](https://www.gairdner.org/images/default-source/default-album/logos/gairdner_logo-red.svg?sfvrsn=4757c219_2) |
| `breakthrough-prize.svg` | Vector; full Breakthrough Prize wordmark | [Wikimedia Commons source and attribution](https://commons.wikimedia.org/wiki/File:Breakthrough_Prize_Logo.svg), [image](https://upload.wikimedia.org/wikipedia/commons/5/54/Breakthrough_Prize_Logo.svg) |
| `abel-prize.jpg` | JPEG, 1240 × 1747; CMYK | [Abel Prize press room](https://abelprize.no/page/press-room), [image](https://abelprize.no/sites/default/files/2022-03/Engelsk%20abel_logo_colours_2014_mindre.jpg) |
| `the-brain-prize.jpg` | JPEG, 1134 × 1134 | [Lundbeck Foundation press release](https://www.prnewswire.com/news-releases/otorgado-el-premio-de-investigacion-cerebral-mas-grande-del-mundo-302704273.html), [original image](https://mma.prnewswire.com/media/2696560/5823277/The_Brain_Prize_logo.jpg?p=original) |
| `lasker-award.svg` | Vector; stacked wordmark from the official mobile header | [Lasker Foundation official website](https://laskerfoundation.org/), [image](https://laskerfoundation.org/wp-content/uploads/2021/01/lasker-logo-text3.svg) |

The Brain Prize and Lasker assets already in `datasets/website/static/logos/` are vectors. Their nominal width and height do not impose a raster resolution limit.
The new Brain Prize JPEG includes the foundation attribution. The new Lasker logo has a more compact aspect ratio than the existing horizontal wordmark.
The Max Planck photograph is soft despite its large pixel dimensions.

## Web copies in `static/logos/`

These originals are kept at full resolution for video and print. The site serves small copies derived from them:

| Web file | Derived how |
| --- | --- |
| `max-planck-medal.png` | trimmed, 160×160, circular transparent crop, 128-colour PNG |
| `abel-prize.png` | head mark only (wordmark dropped), 160×160, white made transparent, 64-colour PNG |
| `the-brain-prize.png` | trimmed, 160×160, white made transparent, 64-colour PNG; inverted in dark mode |
| `breakthrough-prize.svg`, `canada-gairdner-international-award.svg`, `lasker-award.svg` | copied unchanged; Breakthrough inverted in dark mode |
