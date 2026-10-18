"""
Fourth auxiliary vocabulary collection for Daily Lead Agent.
Contains crafts, art media, ingredients, music instruments, woodworking,
CS concepts, science instruments, and creative pursuits.
"""

TRADITIONAL_CRAFTS_ART_MEDIA = [
    # Art Media & Techniques
    "tempera", "encaustic", "gouacheart", "lithography", "mezzotint", "aquatint",
    "intaglio", "reliefprint", "serigraphy", "pyrography", "fretwork", "intarsia",
    "marquetry", "parquetry", "decoupage", "macrameart", "tattinglace", "bobbinlace",
    "needlepoint", "crossstitch", "tapestryweaving", "quiltingtips", "wetfelting", "needlefelting",
    "woolspinning", "loomweaving", "woolcarding", "naturaldyes", "batikcraft", "shiboridye",
    "tiedyetutorial", "jesmonite", "polymerclayart", "airdryclay", "papercrafting", "origamitutorial",
    "kirigami", "paperquilling", "bookbindingdiy", "leatherbinding", "copticstitch", "marblingpaper"
]

CULINARY_SCIENCE_INGREDIENTS = [
    # Fermentation & Preservation
    "sourdoughbread", "kombuchatips", "milkkefir", "waterkefir", "kimchimaking", "sauerkraut",
    "tempehmaking", "misopaste", "kojirice", "nattofood", "quickpickles", "lactoferment",
    "canningbasics", "fooddehydrator", "jerkyrecipes", "meatsmoking", "drycuredmeat", "charcuterieboard",
    "salumimaking", "prosciuttocuring", "pancettacure", "bresaola", "gravlaxsalmon", "duckconfit",
    "porkrillettes", "meatpate", "countryterrine", "sousvidecooking", "gastriquesauce", "demiglacesauce",
    "veloutesauce", "bechamelsauce", "espagnolesauce", "hollandaisesauce", "homemademayonnaise", "garlicaioli",
    "chimichurrisauce", "romescosauce", "salsaverde", "pestogenovese", "olivetapenade", "tzatzikisauce",
    "hummusrecipe", "babaghanoush", "muhammaradip", "labnehcheese", "paneercheese", "halloumicheese",
    "ricottacheese", "freshmozzarella", "burratacheese", "parmesancheese", "pecorinocheese", "cheddarcheese"
]

MUSICAL_INSTRUMENTS_ACOUSTICS = [
    # Folk, World & Acoustic Instruments
    "thereminmusic", "otamatone", "kalimbatabs", "handpanmusic", "hangdrummer",
    "steelpanmusic", "tonguedrum", "marimbamusic", "xylophoneplayer", "vibraphonejazz",
    "glockenspiel", "timpanidrum", "cajonbeat", "djembemaster", "darbukadrum",
    "tablasolo", "bodhrandrum", "tambourineskills", "castanetsplayer", "ukuleletabs",
    "banjotutorial", "mandolintabs", "lutemusic", "bouzoukimusic", "sitarraga",
    "sarodplayer", "kotomusic", "shamisenmusic", "guzhengmusic", "pipaplayer",
    "erhumusic", "dulcimerplayer", "zithermusic", "harptutorial", "accordionmusic",
    "concertinamusic", "melodicatune", "bagpipesmusic", "didgeridooplayer", "ocarinatabs",
    "tinwhistleirish", "panflutemusic", "shakuhachimaster", "bassontutorial", "oboeplayer"
]

WOOD_METAL_FABRICATION_TOOLS = [
    # Fine Woodworking & Carpentry
    "woodjointer", "woodthicknesser", "spindlemoulder", "mortisermachine", "tenonermachine",
    "bandsawresaw", "radialarmsaw", "chopsawtips", "mitersawhacks", "copingsawtips",
    "fretsawart", "dovetailsaw", "tenonsawcutting", "flushcutsaw", "drawknifecarving",
    "spokeshavewood", "blockplaneuse", "jackplaneready", "jointerplanetrue", "smoothingplane",
    "shoulderplane", "routerplanecut", "woodchisels", "carvinggouge", "skewchisel",
    "woodrasp", "rifflerfile", "cardscraper", "burnisherblade", "scratchawl",
    "markinggauge", "mortisegauge", "combinationsquare", "bevelgauge", "springdivider"
]

COMPUTER_SCIENCE_ALGORITHMS = [
    # CS Theory & Fundamentals
    "compilertheory", "interpreterdesign", "transpilerlogic", "bytecodedesign", "assemblerprog",
    "disassemblercode", "decompilertool", "garbagecollector", "memorymanagementc", "heapallocation",
    "stackallocation", "pointerarithmetic", "recursiontree", "iterationlogic", "memoizationtips",
    "dynamicprogramming", "backtrackingalgo", "divideandconquer", "greedyalgorithm", "dijkstraalgorithm",
    "astarpathfinding", "bellmanfordalgo", "kruskalalgorithm", "primalgorithm", "topologicalsort",
    "bitmanipulation", "twopointertechnique", "slidingwindowalgo", "triedatastructure", "fenwicktree",
    "segmenttrees", "avltreebalance", "redblacktree", "btreedatabase", "hashtableimpl",
    "bloomfiltercheck", "graphalgorithms", "depthfirstsearch", "breadthfirstsearch", "shortestpathalgo"
]

SCIENTIFIC_LAB_INSTRUMENTS = [
    # Laboratory & Analytical Equipment
    "spectrophotometer", "centrifugeprep", "electrophoresisgel", "chromatographycolumn", "massspectrometry",
    "xraycrystallography", "calorimeterexpt", "interferometertool", "polarimetertest", "refractometerbrix",
    "viscometertube", "titratorburette", "autoclavesterile", "incubatorculture", "biosafetycabinet",
    "compoundmicroscope", "stereomicroscope", "electronmicroscope", "scanningelectron", "transmissionem",
    "atomicforcemicro", "tunnelingmicro", "reflectortelescope", "refractortelescope", "schmidtcassegrain",
    "dobsoniantelescope", "seismometerdetect", "weatherstationpro", "anemometerwind", "barometerpressure"
]

ALL_EXPANSION_LISTS_4 = [
    TRADITIONAL_CRAFTS_ART_MEDIA,
    CULINARY_SCIENCE_INGREDIENTS,
    MUSICAL_INSTRUMENTS_ACOUSTICS,
    WOOD_METAL_FABRICATION_TOOLS,
    COMPUTER_SCIENCE_ALGORITHMS,
    SCIENTIFIC_LAB_INSTRUMENTS,
]
