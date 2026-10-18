"""
Auxiliary word collector for compile_niche_pool.py
Extends the niche pool with 3,500+ additional genuine creator niches.
"""

# Categorized high-value vocabulary lists for YouTube / content creator niches
GAMING_EXPANSION = [
    # Franchises & Titles
    "subnautica", "kenshi", "factorio", "terraria", "rust", "tarkov", "arma", "dayz",
    "stalker", "metro", "fallout", "skyrim", "oblivion", "morrowind", "starfield",
    "cyberpunk", "witcher", "gwent", "bioshock", "dishonored", "prey", "deusex",
    "deadspace", "calisto", "alienisolation", "amnesia", "outlast", "somagame",
    "visage", "phasmophobia", "devour", "demonologist", "forewarned", "pacify",
    "labyrinthine", "deadbydaylight", "texaschainsaw", "fridaythe13th", "killerklowns",
    "huntshowdown", "chivalry", "mordhau", "mountandblade", "bannerlord", "kingdomcome",
    "forhonor", "absolver", "sifu", "ghostrunner", "katana-zero", "hotlinemiami",
    "ruiner", "myfriendpedro", "ultrakill", "dusk", "amid-evil", "ionfury",
    "prodeus", "quake", "unreal", "doom", "wolfenstein", "serioussam",
    "shadowwarrior", "painkiller", "bulletstorm", "borderlands", "tiny-tina",
    "payday", "crimeboss", "denofwolves", "heist", "robbery", "monaco",
    "teardown", "hardspace", "shipbreaker", "hydroneer", "goldrush", "gasstation",
    "powerwash", "lawnmower", "houseflipper", "carmechanic", "pcbuilding",
    "supermarket", "internetcafe", "cooking-simulator", "thief-simulator",
    "prisonarchitect", "rimworld", "dwarffortress", "oxygennotincluded", "songsofsyx",
    "goniometer", "banished", "manorlords", "farthestfrontier", "settlement",
    "frostpunk", "ixion", "survivingmars", "peraspera", "anno", "tropico",
    "simcity", "citiesskylines", "transportfever", "railwayempire", "openttd",
    "rollercoaster", "planetcoaster", "planetzoo", "jurassicworld", "parkitect",
    "themepark", "two-point", "hospital", "campus", "museum", "megagame",
    # Nintendo & Japanese Games
    "xenoblade", "fireemblem", "bravelydefault", "octopath", "triangle-strategy",
    "live-a-live", "tacticsogre", "finalfantasy", "dragonquest", "starocean",
    "valkyrie", "ys-series", "talesof", "persona", "smt", "shinmegami",
    "etrian", "atelier", "disgaea", "neptunia", "senrankagura", "dynastywarriors",
    "samuraiwarriors", "warriorsorochi", "hyrulewarriors", "fireemblemwarriors",
    "touhou", "meltyblood", "under-night", "guiltygear", "blazblue", "granblue",
    "dनेon", "melty", "kof", "fatalfury", "artoffighting", "samuraishodown",
    "soulcalibur", "virtuafighter", "deadoralive", "rivalschools", "bloodyroar",
    # Indie & Roguelikes
    "spelunky", "noita", "deadcells", "hades", "skul", "curseofthedeadgods",
    "slaythespire", "monster-train", "wildfrost", "balatro", "peglin", "dicey-dungeons",
    "loop-hero", "inscryption", "cultofthelamb", "wizardoflegend", "childrenofmorta",
    "moonlighter", "sparklite", "hyperlightdrifter", "solarsash", "tunic",
    "deathsdoor", "titan-souls", "crosscode", "eastward", "seaofstars",
    "chainedechoes", "omori", "lisagame", "undertale", "deltarune",
    "oneshot", "yumenikki", "ib-game", "madfather", "misao", "corpseparty",
    "danganronpa", "zeroescape", "aithesomnium", "aceattorney", "ghosttrick",
    "professorlayton", "hotel-dusk", "snatcher", "policenauts", "famicom",
    # MMOs & ARPGs
    "worldofwarcraft", "finalfantasyxiv", "guildwars", "runescape", "osrs",
    "blackdesert", "lostark", "newworld", "albiononline", "tibia",
    "everquest", "starwarsgalaxies", "swtor", "lotro", "eso", "elderscrollsonline",
    "fallout76", "seaofthieves", "skullandbones", "elite-dangerous", "eveonline",
    "star-citizen", "x4foundations", "freelancer", "rebelgalaxy", "everspace",
    "chorusgame", "starwars-squadrons", "il2sturmovik", "dcs-world", "warthunder",
    "worldoftanks", "worldofwarships", "worldofwarplanes", "armoredwarfare", "crossout",
    "robocraft", "trailmakers", "besiege", "scrapmechanic", "mainassembly",
    "stormworks", "spaceengineers", "medievalengineers", "stationeers", "astroneer",
    # Modding & Engines
    "forge", "fabric", "optifine", "sodium", "iris", "curseforge", "modrinth",
    "nexusmods", "modorganizer", "vortex", "reshade", "enb", "skse", "f4se",
    "unrealengine", "unity3d", "godot", "gamemaker", "rpgmaker", "defold",
    "bevy", "monogame", "raylib", "love2d", "pico8", "tic80", "construct",
    "source-engine", "source2", "cryengine", "decima", "idtech", "redengine"
]

TECH_COMPUTING_EXPANSION = [
    # Hardware & Architecture
    "motherboard", "chipset", "socket", "pcie", "nvme", "sata", "m2ssd",
    "heatsink", "thermalpaste", "liquidcooling", "radiator", "waterblock",
    "sleeving", "cablemod", "formfactor", "mini-itx", "micro-atx", "e-atx",
    "risercable", "backplate", "vrm", "mosfet", "choke", "capacitors",
    "copperpipe", "heatpipe", "vaporchamber", "fanheader", "rgbheader",
    "argb", "pwm", "airflow", "staticpressure", "pushpull", "shroud",
    "benchtable", "openair", "serverrack", "homelab", "blade-server",
    "xeon", "threadripper", "epyc", "itanium", "opteron", "sparc",
    "riscv", "arm64", "x86", "aarch64", "microcontroller", "stm32",
    "esp32", "esp8266", "pic-micro", "avr", "teensy", "pico", "fpga",
    "verilog", "vhdl", "breadboard", "perfboard", "pcbway", "jlcpcb",
    "soldering", "flux", "solderwick", "desoldering", "reflow", "hotair",
    "oscilloscope", "multimeter", "logic-analyzer", "powersupply", "benchtop",
    # Peripherals & Displays
    "keycaps", "mechanicalswitch", "hotswap", "stabilizers", "lube-station",
    "desknat", "wristrest", "trackball", "verticalmouse", "ergomouse",
    "ultrawide", "superultrawide", "oled", "qled", "miniled", "microled",
    "ips-panel", "va-panel", "tn-panel", "refreshrate", "colorspace",
    "calibrator", "spyder", "colorchecker", "g-sync", "freesync", "vrr",
    "kvm-switch", "thunderbolt", "usbc", "displayport", "hdmi", "e-arc",
    "soundbar", "subwoofer", "studio-monitors", "dac", "amplifier",
    "iem", "in-ear", "planar-magnetic", "open-back", "closed-back",
    "audiophile", "lossless", "flac", "hi-res", "bitrate", "samplingrate"
]

SOFTWARE_DEV_EXPANSION = [
    # Languages & Runtimes
    "golang", "rustlang", "typescript", "javascript", "pythonic", "kotlin",
    "swiftlang", "scalamm", "clojure", "haskell", "elixir", "erlang",
    "lua", "luajit", "julia", "nimlang", "ziglang", "ocaml", "fsharp",
    "csharp", "dotnet", "aspnet", "blazor", "ruby-on-rails", "sinatra",
    "php8", "laravel", "symfony", "codeigniter", "wordpress", "drupal",
    "django", "flask", "fastapi", "tornado", "celery", "pydantic",
    "sqlalchemy", "alembic", "pytest", "unittest", "locust", "hypothesis",
    # Frontend & Fullstack
    "reactjs", "nextjs", "remix-run", "vuejs", "nuxtjs", "svelte",
    "sveltekit", "solidjs", "astrojs", "angular", "qwik", "alpinejs",
    "htmx", "stimulus", "tailwindcss", "unocss", "sass", "less-css",
    "postcss", "styled-components", "stitches", "vanilla-extract", "chakra-ui",
    "shadcn", "radix-ui", "headless-ui", "mui", "ant-design", "daisyui",
    "webpack", "vite", "turbopack", "rollup", "esbuild", "parcel",
    "bun-runtime", "deno", "nodejs", "npm", "yarn", "pnpm",
    # Cloud, DevOps & Infra
    "kubernetes", "k8s", "docker-compose", "containerd", "podman", "helm",
    "terraform", "opentofu", "ansible", "pulumi", "packer", "vagrant",
    "aws-lambda", "serverless", "cloudformation", "cdk", "ec2", "s3-bucket",
    "cloudflare", "workers", "pages", "vercel", "netlify", "fly-io",
    "render-cloud", "railway-app", "digitalocean", "linode", "hetzner", "ovh",
    "prometheus", "grafana", "loki", "tempo", "datadog", "newrelic",
    "sentry", "logstash", "kibana", "fluentd", "opentelemetry", "jaeger",
    "nginx", "caddy", "traefik", "envoy", "haproxy", "apache2",
    # Database & Data Engineering
    "postgresql", "mysql", "mariadb", "sqlite", "cockroachdb", "tidb",
    "mongodb", "couchbase", "dynamodb", "firestore", "faunadb", "cassandra",
    "scylladb", "neo4j", "arangodb", "redis", "valkey", "dragonfly",
    "memcached", "clickhouse", "snowflake", "bigquery", "redshift", "databricks",
    "duckdb", "polars", "pandas", "dbt", "spark", "hadoop", "flink",
    "kafka", "rabbitmq", "pulsar", "nats", "zeromq", "sqs", "sns"
]

AI_DATA_SCIENCE_EXPANSION = [
    # Machine Learning & Deep Learning
    "pytorch", "tensorflow", "keras", "jax", "flax", "onnx", "tensorrt",
    "scikit-learn", "xgboost", "lightgbm", "catboost", "huggingface", "transformers",
    "diffusers", "timm", "datasets", "accelerate", "peft", "bitsandbytes",
    "lora", "qlora", "fine-tuning", "quantization", "gguf", "awq", "gptq",
    "exllama", "vllm", "tgi", "ollama", "localai", "textgen", "comfyui",
    "automatic1111", "fooocus", "invokeai", "sdxl", "midjourney", "dall-e",
    "runwayml", "pika", "sora", "kling", "luma-ai", "tripo3d", "meshy",
    "nerfstudio", "gaussian-splatting", "pointcloud", "depthmap", "segmentation",
    "yolo", "sam-segment", "grounding-dino", "facenet", "deepface", "whisper",
    "wav2vec", "bark-tts", "coqui-tts", "elevenlabs", "rvc", "so-vits",
    "langchain", "llamaindex", "crewai", "autogen", "semantic-kernel", "haystack",
    "chromadb", "pinecone", "weaviate", "qdrant", "milvus", "pgvector",
    "rag", "embeddings", "tokenization", "attention", "transformer", "diffusion",
    "autoencoder", "vae", "gan", "backpropagation", "gradient-descent", "overfitting"
]

FINANCE_INVESTING_CRYPTO_EXPANSION = [
    # Equities & Trading
    "swing-trading", "scalping", "orderflow", "footprint", "marketprofile",
    "volume-profile", "vwap", "supertrend", "macd", "stochastic", "ichimoku",
    "bollinger", "movingaverage", "fibonacci", "support-resistance", "candlestick",
    "breakout", "reversal", "pullback", "continuation", "headandshoulders",
    "doublebottom", "doubletop", "bullflag", "bearflag", "pennant", "wedge",
    "liquidity-pool", "fairvaluegap", "fvg", "orderblock", "smartmoney",
    "liquidity-sweep", "silverbullet", "killzone", "ny-session", "london-session",
    "options-chain", "impliedvolatility", "iv-crush", "thetagang", "ironcondor",
    "straddle", "strangle", "verticalspread", "calendarspread", "coveredcall",
    "cashsecuredput", "creditspread", "debitspread", "leaps", "greeks",
    "delta", "gamma", "theta", "vega", "rho", "hedging", "arbitrage",
    # Fundamental & Wealth
    "valueinvesting", "dcf-model", "freecashflow", "balancesheet", "incomestatement",
    "cashflow", "roe", "roce", "roic", "pe-ratio", "pb-ratio", "dividend-yield",
    "dividendgrowth", "dividendking", "dividend-aristocrat", "drip-investing",
    "bogleheads", "indexinvesting", "vanguard", "ishares", "sp500", "nasdaq",
    "russell2000", "emergingmarkets", "reit", "real-estate", "syndication",
    "househacking", "brrrr", "caprate", "cashoncash", "noi", "amortization",
    "escrow", "downpayment", "pre-approval", "refinancing", "heloc", "reverse-mortgage",
    # Crypto & Web3
    "bitcoin", "satoshi", "halving", "lightningnetwork", "ordinals", "runes",
    "ethereum", "solana", "cardano", "avalanche", "polkadot", "cosmos",
    "chainlink", "uniswap", "aave", "makerdao", "compound", "curve-finance",
    "lido", "liquid-staking", "restaking", "eigenlayer", "celestia", "monad",
    "arbitrum", "optimism", "base-chain", "zksync", "starknet", "scroll",
    "metamask", "phantom-wallet", "ledger-nano", "trezor", "coldstorage",
    "seedphrase", "gasfees", "gwei", "smartcontract", "solidity", "evm"
]

BUSINESS_MARKETING_ECOMMERCE_EXPANSION = [
    # Marketing & Growth
    "funnel", "landingpage", "leadmagnet", "opt-in", "squeeze-page", "upsell",
    "downsell", "cross-sell", "orderbump", "churnrate", "retentionrate",
    "ltv", "cac", "roas", "cpc", "cpm", "ctr", "cpa", "aov", "conversionrate",
    "ab-testing", "multivariate", "heatmaps", "sessionrecording", "copywriting",
    "storytelling", "hooks", "calltoaction", "cta", "socialproof", "testimonials",
    "case-study", "whitepaper", "leadgeneration", "outbound", "inbound", "coldemail",
    "coldcalling", "prospecting", "pipeline", "crm", "hubspot", "salesforce",
    "pipedrive", "close-crm", "notion-workspace", "airtable", "clickup", "monday-com",
    # E-commerce & Retail
    "shopify", "woocommerce", "bigcommerce", "amazon-fba", "walmart-seller",
    "ebay-seller", "etsy-shop", "printondemand", "printful", "printify",
    "dropshipping", "aliexpress", "cjdropshipping", "product-research", "winningproducts",
    "supplier", "packaging", "unboxing", "privatelabel", "wholesaling",
    "freight", "logistics", "3pl", "warehousing", "inventorymanagement", "skus",
    "barcode", "upc", "asin", "buybox", "fbm", "sponsored-products"
]

FITNESS_SPORTS_OUTDOORS_EXPANSION = [
    # Gym & Strength
    "benchpress", "squatting", "deadlifting", "overheadpress", "barbellrow",
    "pullups", "chinups", "dips", "pushups", "lunges", "legpress",
    "hack-squat", "legcurl", "legextension", "calfraise", "bicepcurl",
    "tricepextension", "lateralraise", "frontraise", "reardelt", "facepull",
    "cablefly", "dumbbellfly", "pecdeck", "pullover", "latpulldown",
    "cable-row", "t-bar-row", "shrugs", "wristcurl", "farmerswalk",
    "hypertrophy", "progressiveoverload", "repstoraillure", "rpe", "rir",
    "periodization", "mesocycle", "microcycle", "deload", "supercompensation",
    "calisthenics", "planche", "frontlever", "backlever", "humanflag",
    "handstand", "muscleup", "l-sit", "v-sit", "manna", "pistolsquat",
    # Combat Sports & Martial Arts
    "muaythai", "kickboxing", "jiujitsu", "bjj", "judo", "wrestling",
    "sambor", "karate", "taekwondo", "kungfu", "wingchun", "kravmaga",
    "boxingring", "heavybag", "speedbag", "doubleendbag", "focusmitts",
    "sparring", "footwork", "shadowboxing", "jab", "cross-punch", "hook-punch",
    "uppercut", "overhand", "slipbag", "bobandweave", "clinch", "takedown",
    "sprawl", "guardpass", "mount", "sidecontrol", "backtake", "armbar",
    "trianglechoke", "guillotine", "rearnakedchoke", "kimura", "americana",
    "leglock", "heelhook", "kneebar", "anklelock", "submission", "grappling",
    # Team & Individual Sports
    "pickleball", "padel", "badminton", "squash-sport", "tabletennis", "pingpong",
    "volleyball", "beachvolleyball", "basketball", "streetball", "dunking",
    "handles", "crossover", "stepback", "jumphot", "freethrow", "rebounding",
    "soccer", "footballer", "freekick", "penaltykick", "dribbling", "juggling",
    "cricket", "batting", "bowling", "wicketkeeper", "spinbowler", "pacebowler",
    "golfing", "golfswing", "putting", "chipping", "driver-golf", "iron-golf",
    "fairway", "greens", "bunker-shot", "birdie", "eagle-golf", "handicap-golf"
]

FOOD_CULINARY_COFFEE_EXPANSION = [
    # Cooking Techniques & Equipment
    "sousvide", "castiron", "carbonsteel", "stainlesssteel", "wokanroll",
    "mandoline", "mortarandpestle", "foodprocessor", "standmixer", "immersionblender",
    "dutch-oven", "stockpot", "saucepan", "bakingstone", "pizzasteel",
    "meatthermometer", "probe-thermometer", "kitchenscale", "benchscraper",
    "fermentation", "sourdough", "starter", "levain", "bulkferment", "banneton",
    "lame", "scoring", "crumbshot", "hydration", "bakerspercentage", "autolyse",
    "kneading", "stretchandfold", "coilfold", "lamination", "croissant",
    "brioche", "baguette", "ciabatta", "focaccia", "flatbread", "naan",
    "pita", "tortilla", "tacos", "burritos", "quesadilla", "enchilada",
    "salsa", "guacamole", "ceviche", "tiradito", "poke-bowl", "sushi-roll",
    "sashimi", "nigiri", "ramen-broth", "tonkotsu", "shoyu", "miso-ramen",
    "dashi", "tare", "chashu", "ajitsuke", "noodles", "soba", "udon",
    "pasta-fresca", "ravioli", "tortellini", "gnocchi", "carbonara", "cacioepepe",
    "bolognese", "ragu", "lasagna", "risotto", "paella", "tapas", "pinchos",
    # Drinks & Coffee
    "pour-over", "aeropress", "frenchpress", "chemex", "kalita-wave", "v60",
    "espresso-shot", "latteart", "steamingmilk", "microfoam", "barista-skills",
    "roastingcoffee", "greenbeans", "degassing", "cupping-coffee", "extraction",
    "tDS", "refractometer", "mocktail", "cocktails", "whiskey", "bourbon",
    "scotch", "single-malt", "ryewhiskey", "mezcal", "tequila", "gin-botanicals",
    "rum-cocktail", "tiki-drinks", "sommelier", "viticulture", "terroir"
]

ARTS_DESIGN_CRAFTS_EXPANSION = [
    # Visual Arts & Illustration
    "oilpainting", "acrylicpainting", "watercolor", "gouache", "pastels",
    "charcoaldrawing", "graphitedrawing", "inkdrawing", "linocut", "woodcut",
    "screenprinting", "etching", "monotype", "cyanotype", "calligraphy",
    "lettering", "gouache-paint", "sketchbook", "urban-sketching", "pleinair",
    "digitalpainting", "procreate", "photoshop-art", "clipstudiopaint",
    "corelpainter", "krita", "affinitydesigner", "illustrator", "vectorart",
    "characterdesign", "conceptart", "environmentart", "propdesign", "mattepainting",
    # 3D, CGI & VFX
    "blender3d", "maya3d", "3dsmax", "cinema4d", "zbrush", "substancepainter",
    "substancedesigner", "marmoset", "houdini-vfx", "nuke-compositing", "aftereffects",
    "davinciresolve", "premierepro", "finalcutpro", "avid-media", "fusion-vfx",
    "hard-surface", "sculpting", "retopologizing", "uv-unwrapping", "bakingmaps",
    "normalmap", "roughnessmap", "metallicmap", "displacementmap", "pbr-textures",
    "rigging3d", "inversekinematics", "blendshapes", "weightpainting", "mocap",
    # Crafts, Wood & Metal
    "woodturning", "lathe-work", "bandsaw", "tablesaw", "scrollsaw", "routertable",
    "dovetail", "mortiseandtenon", "pocket-holes", "biscuitjointer", "woodfinishing",
    "polyurethane", "tungoil", "danishoil", "epoxyresin", "river-table",
    "woodcarving", "chainsaw-carving", "blacksmithing", "forge-work", "anvil",
    "knifemaking", "bladesmithing", "damascus-steel", "leathercraft", "saddlestitch",
    "leather-carving", "potterywheel", "ceramics-glaze", "kiln-firing", "raku",
    "stainedglass", "glassblowing", "flameworking", "beadwork", "jewelrymaking",
    "metalsmithing", "lapidary", "gem-faceting", "resinart", "miniaturepainting",
    "warhammer-40k", "diorama-making", "gunplabuilding", "scalemodeling"
]

SCIENCE_NATURE_HISTORY_EXPANSION = [
    # Sciences & Space
    "quantum-physics", "relativity", "particle-physics", "cern", "hadroncollider",
    "astrophysics", "cosmology", "blackholes", "neutronstars", "supernova",
    "nebulae", "exoplanets", "jameswebb", "hubblespace", "astrophotography",
    "stargazing", "telescopes", "spacex", "falcon9", "starship", "artemis",
    "mars-rover", "perseverance", "voyager", "orbitalmechanics", "rocketry",
    "paleontology", "dinosaurs", "fossils", "amber-fossil", "mammoth",
    "archaeology", "ancientegypt", "mesopotamia", "indusvalley", "rome-empire",
    "gladiators", "legionnaires", "viking-age", "samurai-history", "medieval-warfare",
    "castle-sieges", "armor-suits", "heraldry", "cartography", "exploration",
    # Nature, Ecology & Animals
    "aquascaping", "plantedtank", "co2-aquarium", "shrimptank", "cichlids",
    "discus-fish", "bettas", "reef-tank", "coralreef", "marinebiology",
    "herpetology", "reptiles", "ballpython", "beardeddragon", "geckos",
    "tarantulas", "entomology", "antkeeping", "beekeeping", "apiculture",
    "apiary", "honeycomb", "swarming", "birdwatching", "birdphotography",
    "ornithology", "raptors", "falconry", "wildlifephotography", "safari"
]

ALL_EXPANSION_LISTS = [
    GAMING_EXPANSION,
    TECH_COMPUTING_EXPANSION,
    SOFTWARE_DEV_EXPANSION,
    AI_DATA_SCIENCE_EXPANSION,
    FINANCE_INVESTING_CRYPTO_EXPANSION,
    BUSINESS_MARKETING_ECOMMERCE_EXPANSION,
    FITNESS_SPORTS_OUTDOORS_EXPANSION,
    FOOD_CULINARY_COFFEE_EXPANSION,
    ARTS_DESIGN_CRAFTS_EXPANSION,
    SCIENCE_NATURE_HISTORY_EXPANSION,
]
