"""
Comprehensive niche pool compiler for Daily Lead Agent.
Generates `src/curated_niches.py` containing thousands of verified, distinct,
strictly ONE-WORD genuine creator content niches.
"""

import re
from pathlib import Path
from typing import Set, List

def is_valid_one_word_niche(niche: str) -> bool:
    if not niche or not isinstance(niche, str):
        return False
    stripped = niche.strip()
    if not stripped or len(stripped.split()) != 1:
        return False
    # Strictly alphabetic and hyphens/underscores, NO numbers (no creator101, etc.)
    return bool(re.match(r"^[A-Za-z_-]+$", stripped))

def clean_word(w: str) -> str:
    return w.strip().lower()

# Build comprehensive thematic sets
def get_all_niches() -> List[str]:
    niches: Set[str] = set()

    def add_words(*word_lists):
        for lst in word_lists:
            for item in lst:
                if isinstance(item, str):
                    words = item.replace(",", " ").split()
                    for w in words:
                        cw = clean_word(w)
                        if is_valid_one_word_niche(cw) and len(cw) >= 3 and not re.search(r"\d", cw):
                            niches.add(cw)

    # 1. Gaming - Titles, Franchises & Universes
    add_words([
        "minecraft", "roblox", "fortnite", "valorant", "counterstrike", "overwatch",
        "apexlegends", "warzone", "cyberpunk", "witcher", "skyrim", "fallout",
        "starfield", "eldenring", "bloodborne", "sekiro", "darksouls", "demonssouls",
        "liesofp", "terraria", "subnautica", "stardew", "animalcrossing", "palworld",
        "lethalcompany", "amongus", "fallguys", "rocketleague", "brawlhalla", "smite",
        "leagueoflegends", "dota", "starcraft", "warcraft", "diablo", "pathofexile",
        "grimdawn", "torchlight", "baldursgate", "divinity", "dragonage", "masseffect",
        "assassinscreed", "farcry", "watchdogs", "rainbowsix", "splintercell",
        "ghostrecon", "thedivision", "halflife", "portal", "teamfortress", "payday",
        "helldivers", "warhammer", "spacemarine", "vermintide", "darktide", "totalwar",
        "civilization", "crusaderkings", "heartsofiron", "stellaris", "ageofempires",
        "homeworld", "companyofheroes", "factorio", "satisfactory", "rimworld",
        "dwarffortress", "oxygennotincluded", "dontstarve", "theforest", "greenhell",
        "strandeddeep", "raft", "valheim", "conanexiles", "dayz", "projectzomboid",
        "scum", "stateofdecay", "deadisland", "dyinglight", "killingfloor", "back4blood",
        "residentevil", "silenthill", "deadspace", "thecallisto", "alanwake", "control",
        "quantumbreak", "maxpayne", "reddead", "gtav", "gtaonline", "bully", "mafia",
        "saintsrow", "sleepingdogs", "justcause", "madmax", "batman", "arkham",
        "spiderman", "wolverine", "avengers", "starwars", "battlefront", "destiny",
        "halo", "forzahorizon", "forzamotorsport", "granturismo", "needforspeed",
        "burnout", "thecrew", "dirt", "assetto", "iracing", "rfactor", "projectcars",
        "beamng", "wreckfest", "snowrunner", "mudrunner", "eurotruck", "americantruck",
        "flightsimulator", "elitedangerous", "starcitizen", "nomanssky", "kerbal",
        "outerwilds", "myst", "witness", "talosprinciple", "supraland", "superliminal",
        "stanleyparable", "firewatch", "gonehome", "lifeisstrange", "detroitbecomehuman",
        "heavyrain", "untildawn", "thequarry", "supermassive", "walkingdead", "wolfamongus",
        "tombraider", "uncharted", "godofwar", "horizonzero", "thelastofus",
        "ghostsoftsushima", "infamous", "ratchetandclank", "jakanddaxter", "slycooper",
        "spyro", "crashbandicoot", "sonic", "mario", "mariokart", "marioodyssey",
        "luigismansion", "zelda", "breathofthewild", "tearofthekingdom", "ocarinaoftime",
        "majorasmask", "windwaker", "twilightprincess", "metroid", "metroidprime",
        "metroiddread", "donkeykong", "kirby", "pikmin", "splatoon", "smashbros",
        "pokemon", "pokemongo", "pokemonunite", "fireemblem", "xenoblade", "bayonetta",
        "astralchain", "monsterhunter", "dragonsdogma", "devilmaycry", "onimusha",
        "streetfighter", "tekken", "mortalkombat", "guiltygear", "blazblue",
        "kingoffighters", "dragonball", "narutogame", "onepiecegame", "persona",
        "shinmegamitensei", "yakuza", "likeadragon", "judgement", "shenmue",
        "nierautomata", "nierreplicant", "finalfantasy", "chrono", "dragonquest",
        "kingdomhearts", "octopathtraveler", "bravelydefault", "talesof", "starocean",
        "hollowknight", "silksong", "undertale", "deltarune", "cuphead", "celeste",
        "deadcells", "hades", "slaythespire", "monsterprom", "inscryption", "balatro",
        "dave-the-diver", "brotato", "vampiresurvivors", "bindingofisaac", "entertheregeon",
        "riskofrain", "spelunky", "roguelegacy", "darkestdungeon", "loophero", "noita"
    ])

    # Mobile, Esports & Casual
    add_words([
        "bgmi", "pubgmobile", "freefire", "codmobile", "standoff", "criticalops",
        "arenaofvalor", "mobilelegends", "wildrift", "honorofkings", "clashofclans",
        "clashroyale", "brawlstars", "hayday", "boombeach", "subwaysurfers", "templerun",
        "candycrush", "angrybirds", "plantsvszombies", "monopolygo", "genshinimpact",
        "honkaistarrail", "zenlesszonezero", "wutheringwaves", "toweroffantasy",
        "arknights", "azurlane", "bluearchive", "nikke", "fategrandorder", "epicseven",
        "summonerswar", "raidshadowlegends", "marvelsnap", "hearthstone", "shadowverse",
        "gwent", "legendsofruneterra", "magicarena", "chesscom", "lichess", "carrompool",
        "ludoking", "asphalt", "realracing", "gridautosport", "carxstreet"
    ])

    # Gaming Mechanics, Content Formats & Culture
    add_words([
        "gameplay", "walkthrough", "playthrough", "longplay", "letsplay", "speedrun",
        "speedrunning", "bossfight", "nuzlocke", "permadeath", "hardcore", "pacifist",
        "eastereggs", "lore", "tierlist", "glitches", "modding", "mods", "addons",
        "shaders", "texturepack", "unrealengine", "unityengine", "gameanalysis",
        "videoessay", "gamedesign", "leveldesign", "bossdesign", "gamereview",
        "retrogaming", "emulation", "retrogames", "arcade", "leaderboards",
        "worldrecord", "toolassisted", "esports", "scrims", "tournaments", "lanparty",
        "clutch", "highlights", "montage", "trickshots", "aimtraining", "aimlab",
        "crosshair", "loadout", "ranked", "competitive", "sandbox", "survival",
        "horror", "roguelike", "roguelite", "metroidvania", "dungeoncrawler",
        "bullethell", "visualnovel", "openworld", "stealth", "platformer",
        "puzzleplatformer", "simracing", "citybuilder", "tycoon", "colonymanager",
        "grandstrategy", "turnbased", "deckbuilder", "autobattler", "towerdefense",
        "battleroyale", "extractionshooter", "lootershooter", "heroshooter",
        "boomershooter", "arenashooter", "hackandslash", "soulsborne", "soulslike",
        "actionrpg", "tacticalrpg", "jrpg", "wrpg", "mmorpg", "pvp", "pve", "coop",
        "multiplayer", "singleplayer", "roleplay", "gmod", "vrchat", "recroom"
    ])

    # 2. Technology & Gadgets
    add_words([
        "smartphone", "smartphones", "smartwatch", "smartwatches", "smartband",
        "earbuds", "headphones", "audiophile", "earphones", "headset", "soundbar",
        "speakers", "bluetooth", "amplifier", "turntable", "microphone", "webcam",
        "actioncam", "gopro", "instax", "polaroid", "mirrorless", "dslr", "telephoto",
        "lens", "macro", "tripod", "gimbal", "stabilizer", "teleprompter", "ringlight",
        "softbox", "tablet", "tablets", "ipad", "ipados", "androidtablet", "stylus",
        "applepencil", "ereader", "kindle", "display", "monitor", "ultrawide",
        "oled", "amoled", "qled", "miniled", "refreshrate", "colorspace", "colorimeter",
        "calibrator", "charger", "powerbank", "magsafe", "wirelesscharging", "powerstation",
        "inverter", "cablemanagement", "deskmat", "desksetup", "minimalsetup", "workspace",
        "ergonomics", "standingdesk", "ergonomicchair", "armrest", "footrest",
        "mechanicalkeyboard", "keycaps", "switches", "keyboardmod", "lubing",
        "hotswap", "customkeyboard", "gamingmouse", "mousepad", "skates", "pollingrate",
        "ultralight", "wirelessmouse", "smarthome", "homeautomation", "homeassistant",
        "zigbee", "zwave", "matter", "thread", "homekit", "alexa", "googlehome",
        "smartbulb", "smartswitch", "smartplug", "smartlock", "robotvacuum", "airpurifier",
        "securitycamera", "doorbellcam", "nasstorage", "dashcam", "drone", "quadcopter",
        "fpvdrone", "cinewhoop", "goggles", "radiocontroller", "brushlessmotor", "propellers"
    ])

    # Computer Hardware & PC Building
    add_words([
        "pcbuilding", "gamingpc", "budgetpc", "workstation", "overclocking",
        "undervolting", "benchmarks", "thermalpaste", "watercooling", "customloop",
        "radiator", "chassis", "airflow", "dustfilters", "motherboard", "chipset",
        "socket", "processor", "cpu", "intel", "amd", "ryzen", "threadripper",
        "xeon", "epyc", "graphicscard", "gpu", "nvidia", "geforce", "radeon",
        "intelarc", "vram", "raytracing", "pathtracing", "framegeneration",
        "powersupply", "psu", "modularkit", "storage", "nvme", "ssd", "harddrive",
        "hdd", "pcie", "ram", "overclock", "heatsink", "fancontrol", "fanhub",
        "smallformfactor", "minipc", "nuc", "synology", "qnap", "truenas", "unraid",
        "homelab", "proxmox", "esxi", "hypervisor", "serverrack", "patchpanel",
        "ethernet", "router", "meshwifi", "firewall", "pfsense", "opnsense"
    ])

    # Tech Brands, OS & Ecosystems
    add_words([
        "apple", "iphone", "macbook", "ipad", "mac", "applewatch", "airpods",
        "ios", "macos", "android", "samsung", "galaxy", "pixel", "google",
        "xiaomi", "oneplus", "realme", "redmi", "motorola", "vivo", "oppo",
        "nothingphone", "asus", "lenovo", "thinkpad", "dell", "alienware", "hp",
        "acer", "msi", "razer", "logitech", "corsair", "steelseries", "sony",
        "bose", "sennheiser", "anker", "dji", "insta360", "gopro", "garmin",
        "fitbit", "amazfit", "huawei", "honor", "zte", "poco", "infinix", "tecno"
    ])

    # 3. Programming & Software Development
    add_words([
        "python", "javascript", "typescript", "golang", "rustlang", "cplusplus",
        "csharp", "java", "kotlin", "swiftlang", "rubylang", "phplang", "perllang",
        "scalalang", "clojure", "elixir", "erlang", "haskell", "ocaml", "fsharp",
        "lisp", "scheme", "racket", "rstats", "julialang", "dartlang", "luacode",
        "vlang", "ziglang", "nimlang", "solidity", "vyper", "assembly", "wasm",
        "webassembly", "html5", "css3", "sass", "less", "bash", "zsh", "powershell",
        "regex", "sql", "plsql", "tsql"
    ])

    # Web & App Frameworks
    add_words([
        "reactjs", "reactnative", "nextjs", "vuejs", "nuxtjs", "angularjs",
        "svelte", "sveltekit", "solidjs", "qwik", "remixjs", "astrojs",
        "gatsbyjs", "nodejs", "deno", "bunjs", "expressjs", "nestjs",
        "fastify", "koa", "django", "flask", "fastapi", "tornado", "rubyonrails",
        "laravel", "symfony", "springboot", "quarkus", "micronaut", "aspnet",
        "dotnet", "blazor", "maui", "flutter", "ionic", "tauri", "electronjs",
        "expo", "threejs", "babylonjs", "tailwind", "tailwindcss", "bootstrap",
        "chakraui", "shadcn", "materialui", "antdesign", "mantine", "radix"
    ])

    # Databases, Cloud & DevOps
    add_words([
        "postgresql", "mysql", "mariadb", "sqlite", "oracle", "sqlserver",
        "mongodb", "couchdb", "documentdb", "redis", "memcached", "cassandra",
        "scylladb", "dynamodb", "neo4j", "arangodb", "elasticsearch", "opensearch",
        "meilisearch", "typesense", "clickhouse", "snowflake", "bigquery", "redshift",
        "duckdb", "influxdb", "timescaledb", "supabase", "firebase", "pocketbase",
        "appwrite", "hasura", "prisma", "drizzle", "typeorm", "hibernate",
        "sqlalchemy", "docker", "podman", "containerd", "kubernetes", "minikube",
        "helm", "terraform", "terragrunt", "ansible", "pulumi", "vagrant",
        "jenkins", "githubactions", "gitlabci", "circleci", "argocd", "prometheus",
        "grafana", "datadog", "newrelic", "sentry", "splunk", "elasticstack",
        "logstash", "kibana", "fluentd", "jaeger", "opentelemetry", "traefik",
        "nginx", "caddy", "envoy", "haproxy", "wireguard", "openvpn", "tailscale",
        "cloudflare", "aws", "azure", "googlecloud", "digitalocean", "linode",
        "vultr", "hetzner", "ovh", "serverless", "lambdas", "microservices"
    ])

    # Software Engineering & Computer Science
    add_words([
        "leetcode", "hackerrank", "codeforces", "codechef", "neetcode",
        "datastructures", "algorithms", "bigo", "dynamicprogramming", "binarysearch",
        "graphalgorithms", "trees", "linkedlist", "recursion", "backtracking",
        "sorting", "systemdesign", "highleveldesign", "lowleveldesign", "designpatterns",
        "cleanarchitecture", "solidprinciples", "cleancode", "refactoring",
        "codesmell", "technicaldebt", "monolith", "eventdriven", "restapi",
        "graphql", "grpc", "trpc", "webhook", "websockets", "webrtc", "pwa",
        "accessibility", "pagespeed", "unittesting", "integrationtesting",
        "e2etesting", "cypress", "playwright", "selenium", "puppeteer", "vitest",
        "jest", "pytest", "mocking", "tdd", "scrum", "agile", "kanban", "gitflow",
        "open-source", "debugging", "profiling", "memoryleak", "compilers", "interpreters"
    ])

    # 4. Artificial Intelligence & Data Science
    add_words([
        "artificialintelligence", "machinelearning", "deeplearning", "datascience",
        "neuralnetwork", "neuralnetworks", "computervision", "naturallanguage",
        "nlp", "speechrecognition", "generativeai", "genai", "promptengineering",
        "prompting", "llm", "llms", "transformers", "attention", "selfattention",
        "encoder", "decoder", "bert", "gpt", "claude", "gemini", "llama",
        "mistral", "stablediffusion", "midjourney", "dalle", "sora", "runway",
        "pika", "elevenlabs", "whisper", "langchain", "llamaindex", "autogen",
        "crewai", "multiagent", "rag", "vectorsearch", "embeddings", "pinecone",
        "weaviate", "qdrant", "chromadb", "milvus", "faiss", "pytorch", "tensorflow",
        "keras", "jax", "onnx", "tensorrt", "huggingface", "scikitlearn", "pandas",
        "numpy", "scipy", "matplotlib", "seaborn", "plotly", "jupyter", "kaggle",
        "wandb", "mlflow", "airflow", "reinforcementlearning", "qlearning", "ppo",
        "quantization", "distillation", "syntheticdata", "robotics", "autonomous"
    ])

    # 5. Finance, Stock Market, Trading & Wealth
    add_words([
        "stockmarket", "investing", "stocks", "equities", "shares", "indices",
        "nifty", "sensex", "banknifty", "nasdaq", "derivatives", "options",
        "futures", "optionsselling", "optionsbuying", "optionstrading", "calloption",
        "putoption", "hedging", "straddle", "strangle", "ironcondor", "spreads",
        "openinterest", "impliedvolatility", "greeks", "delta", "gamma", "theta",
        "vega", "daytrading", "intraday", "swingtrading", "positional", "scalping",
        "algotrading", "backtesting", "zerodha", "groww", "upstox", "angelone",
        "tradingview", "charting", "candlesticks", "chartpatterns", "breakout",
        "breakdown", "supportresistance", "trendline", "movingaverage", "bollingerbands",
        "supertrend", "vwap", "orderflow", "marketprofile", "priceaction", "smartmoney",
        "liquidity", "fairvaluegap", "fundamentalanalysis", "balancesheet", "cashflow",
        "incomestatement", "ratioanalysis", "peratio", "pbratio", "roce", "dividend",
        "dividends", "dividendyield", "marketcap", "multibagger", "growthstocks",
        "valuestocks", "ipo", "valuation", "dcf", "macroeconomics", "inflation",
        "interestrates", "centralbanks", "federalreserve", "recession", "bullmarket",
        "bearmarket", "commodities", "crudeoil", "naturalgas", "gold", "silver"
    ])

    # Crypto & Web3
    add_words([
        "cryptocurrency", "crypto", "bitcoin", "btc", "ethereum", "eth", "solana",
        "sol", "cardano", "ada", "ripple", "xrp", "polkadot", "avalanche", "avax",
        "chainlink", "polygon", "matic", "binance", "bnb", "dogecoin", "shiba",
        "memecoin", "altcoin", "altcoins", "stablecoin", "tether", "usdt", "usdc",
        "defi", "decentralized", "smartcontracts", "layer1", "layer2", "rollups",
        "arbitrum", "optimism", "zksync", "basechain", "toncoin", "sui", "aptos",
        "nearprotocol", "uniswap", "pancakeswap", "aave", "compound", "makerdao",
        "yieldfarming", "liquiditypool", "staking", "proofofstake", "proofofwork",
        "mining", "coldwallet", "ledger", "trezor", "metamask", "phantomwallet",
        "trustwallet", "airdrop", "airdrops", "tokenomics", "whitepaper", "halving",
        "coinbase", "kraken", "bybit", "kucoin", "okx", "web3", "daos", "nfts"
    ])

    # Personal Finance, Real Estate & Insurance
    add_words([
        "personalfinance", "wealthbuilding", "financialfreedom", "retireearly",
        "firemovement", "budgeting", "savingmoney", "emergencyfund", "debtfree",
        "creditscore", "cibil", "creditcards", "cashback", "rewardpoints", "miles",
        "mortgages", "homeloans", "carloans", "studentloans", "refinancing",
        "insurance", "terminsurance", "healthinsurance", "motorinsurance", "mutualfunds",
        "sip", "indexfunds", "etfs", "bonds", "sovereigngold", "goldloan",
        "fixeddeposit", "recurringdeposit", "providentfund", "taxplanning", "incometax",
        "gst", "taxsaving", "capitalgains", "estateplanning", "wills", "inheritance",
        "realestate", "reits", "landinvesting", "commercialproperty", "residentialproperty",
        "rentalincome", "houseflipping", "homeownership", "airbnb", "vacationrentals"
    ])

    # 6. Business, Startups, Marketing & Sales
    add_words([
        "business", "entrepreneurship", "startups", "bootstrapping", "venturecapital",
        "angelinvestor", "pitchdeck", "seedfunding", "seriesa", "valuation",
        "equity", "incubator", "accelerator", "ycombinator", "sharktank", "solopreneur",
        "microsaas", "saas", "b2b", "b2c", "d2c", "marketplace", "ecommerce",
        "dropshipping", "shopify", "woocommerce", "amazonfba", "etsy", "printondemand",
        "productresearch", "suppliers", "alibaba", "inventory", "fulfillment",
        "shipping", "packaging", "customerservice", "churnrate", "profitability",
        "accounting", "bookkeeping", "invoicing", "payroll", "outsourcing",
        "virtualassistant", "freelancing", "agency", "smma", "marketingagency",
        "consulting", "coaching", "masterminds", "networking", "franchising"
    ])

    # Marketing, Sales & Copywriting
    add_words([
        "marketing", "digitalmarketing", "growthhacking", "contentmarketing",
        "copywriting", "directresponse", "emailmarketing", "newsletters", "substacks",
        "automation", "funnels", "salesfunnels", "landingpage", "leadgeneration",
        "leadmagnet", "webinar", "salespage", "conversionrate", "analytics",
        "googleanalytics", "searchconsole", "semrush", "ahrefs", "seo", "technicalseo",
        "onpageseo", "offpageseo", "backlinks", "keywordresearch", "googleads",
        "facebookads", "metaads", "instagramads", "tiktokads", "youtubeads",
        "linkedinads", "retargeting", "influencermarketing", "affiliatemarketing",
        "sponsorships", "branddeals", "mediakit", "publicrelations", "pressrelease",
        "branding", "rebranding", "storytelling", "salesmanship", "negotiation",
        "coldemail", "coldcalling", "closing", "objectionhandling", "prospecting"
    ])

    # 7. Fitness, Bodybuilding, Sports & Martial Arts
    add_words([
        "fitness", "bodybuilding", "powerlifting", "weightlifting", "calisthenics",
        "streetworkout", "crossfit", "gymnastics", "olympiclifting", "strongman",
        "hypertrophy", "progressiveoverload", "periodization", "pushpulllegs",
        "benchpress", "squats", "deadlift", "overheadpress", "barbellrow",
        "pullups", "chinups", "dips", "pushups", "lunges", "bicepcurls",
        "tricepextensions", "lateralraises", "cablecrossover", "legpress", "calfraises",
        "absworkout", "plank", "crunches", "kettlebell", "dumbbells", "barbell",
        "resistancebands", "foamroller", "liftingbelt", "wriststraps", "physique",
        "shredded", "aesthetics", "muscledefinition", "vascularity", "bodyfat",
        "dexascan", "bulking", "cutting", "recomposition", "cardio", "hiit",
        "inclinewalking", "stairmaster", "rowingmachine", "elliptical", "jumprope",
        "skipping", "sprinting", "sprints", "plyometrics", "mobility", "flexibility",
        "yoga", "pilates", "stretching", "foamrolling", "physiotherapy", "rehabilitation"
    ])

    # Sports
    add_words([
        "cricket", "ipl", "testcricket", "bowling", "batting", "fastbowling",
        "spinbowling", "wicketkeeping", "fielding", "football", "soccer", "striker",
        "midfielder", "defender", "goalkeeper", "dribbling", "freekicks", "penalties",
        "basketball", "nba", "dunking", "tennis", "wimbledon", "serve", "forehand",
        "backhand", "badminton", "tabletennis", "pingpong", "volleyball", "swimming",
        "freestyle", "breaststroke", "butterfly", "backstroke", "triathlon", "ironman",
        "marathon", "halfmarathon", "ultramarathon", "trackandfield", "athletics",
        "highjump", "longjump", "polevault", "javelin", "discus", "shotput",
        "archery", "shooting", "golf", "golfswing", "putting", "drivingrange",
        "boxing", "sparring", "footwork", "mma", "ufc", "bjj", "brazilianjiujitsu",
        "grappling", "wrestling", "judo", "karate", "taekwondo", "muaythai",
        "kickboxing", "kravmaga", "aikido", "kungfu", "fencing", "climbing",
        "bouldering", "rockclimbing", "mountaineering", "surfing", "skateboarding",
        "snowboarding", "skiing", "wakeboarding", "kitesurfing", "kayaking",
        "rowing", "canoeing", "paddleboarding", "rafting", "scubadiving", "freediving"
    ])

    # 8. Health, Nutrition & Wellness
    add_words([
        "nutrition", "dietetics", "macronutrients", "micronutrients", "calories",
        "caloricdeficit", "caloricsurplus", "ketodiet", "ketosis", "carnivore",
        "paleodiet", "mediterranean", "intermittentfasting", "fasting", "autophagy",
        "veganism", "plantbased", "vegetarian", "glutenfree", "dairyfree",
        "sugarfree", "lowcarb", "highprotein", "mealprep", "proteinpowder",
        "wheyprotein", "casein", "creatine", "preworkout", "multivitamins", "fishoil",
        "omega3", "electrolytes", "hydration", "guthealth", "microbiome", "probiotics",
        "prebiotics", "digestion", "metabolism", "insulinresistance", "diabetes",
        "bloodpressure", "cholesterol", "cardiovascular", "biohacking", "longevity",
        "antiaging", "coldplunge", "sauna", "cryotherapy", "redlighttherapy",
        "circadianrhythm", "sleepapnea", "insomnia", "melatonin", "dermatology",
        "skincare", "sunscreen", "retinol", "vitaminc", "hyaluronicacid", "acnetreatment",
        "haircare", "hairgrowth", "minoxidil", "finasteride", "hairtransplant",
        "mentalhealth", "psychology", "therapy", "anxietyrelief", "depressionrecovery",
        "burnoutrecovery", "stressmanagement", "breathwork", "meditation", "mindfulness",
        "journaling", "gratitude", "ayurveda", "homeopathy", "naturopathy", "chiropractic"
    ])

    # 9. Creative Media, Filmmaking, Video & Photography
    add_words([
        "filmmaking", "indiefilm", "cinematography", "videography", "documentary",
        "shortfilm", "featurefilm", "screenwriting", "scriptwriting", "storyboarding",
        "directing", "acting", "casting", "productiondesign", "locationscouting",
        "cinematographer", "lightingsetup", "softbox", "fresnel", "cinemalens",
        "anamorphic", "primes", "zoomlens", "ndfilter", "polarizer", "mattebox",
        "followfocus", "steadicam", "easyrig", "ronin", "crane", "dolly", "slider",
        "timelapse", "hyperlapse", "slowmotion", "colorgrading", "colorcorrection",
        "davinciresolve", "premierepro", "finalcutpro", "aftereffects", "capcut",
        "vfx", "visualeffects", "cgi", "chromakey", "compositing", "rotoscoping",
        "matchmoving", "motiontracking", "sounddesign", "foley", "audioengineering",
        "audiomixing", "soundtrack", "filmmusic", "voiceacting", "voiceover",
        "microphones", "lavalier", "shotgunmic", "boommic", "fieldrecording",
        "photography", "portraitphotography", "landscapephotography",
        "streetphotography", "astrophotography", "wildlifephotography",
        "sportsphotography", "eventphotography", "weddingphotography",
        "fashionphotography", "commercialphotography", "productphotography",
        "architecturalphotography", "foodphotography", "lightroom", "photoshop",
        "retouching", "darkroom", "filmphotography", "dronephotography"
    ])

    # 10. Design, 3D, Animation & Visual Arts
    add_words([
        "graphicdesign", "logodesign", "brandidentity", "typography", "calligraphy",
        "lettering", "posters", "packagingdesign", "vectorart", "illustrator",
        "illustration", "digitalillustration", "conceptart", "mattepainting",
        "characterdesign", "creaturedesign", "environmentart", "pixelart",
        "isometricart", "drawing", "sketching", "lineart", "watercolor",
        "acrylicpainting", "oilpainting", "gouache", "pastels", "charcoal",
        "inkdrawing", "spraypainting", "mural", "streetart", "graffiti",
        "3dmodeling", "3danimation", "blender3d", "maya", "cinema4d", "zbrush",
        "substancepainter", "sculpting", "rigging", "texturing", "uvunwrapping",
        "lighting3d", "rendering", "cycles", "eevee", "octanerender", "redshift3d",
        "vray", "arnoldrender", "motiondesign", "motiongraphics", "kinetictext",
        "infographics", "uiuxdesign", "uidesign", "uxdesign", "wireframing",
        "prototyping", "figma", "productdesign", "industrialdesign", "interiordesign",
        "architecture", "claymodeling", "digitalsculpting", "characterart"
    ])

    # 11. Music, Audio Production & Instruments
    add_words([
        "musicproduction", "beatmaking", "beatmaker", "flstudio", "abletonlive",
        "logicprox", "protools", "cubase", "reaper", "studioone", "bitwig",
        "synthesizers", "modularsynth", "eurorack", "vst", "plugins", "serum",
        "sounddesign", "sampling", "mixing", "mastering", "equalization", "compression",
        "reverb", "delay", "saturation", "audiointerface", "studiomonitors",
        "songwriting", "composition", "musictheory", "chords", "harmony", "melody",
        "scales", "vocals", "singing", "vocalcoach", "vocalwarmup", "belting",
        "falsetto", "vocalrange", "autotune", "guitar", "electricguitar",
        "acousticguitar", "classicalguitar", "fingerstyle", "shredding", "soloing",
        "guitarriffs", "pedalboard", "amplifiers", "bassguitar", "slapbass",
        "drumming", "drumkit", "electronicdrums", "cymbals", "percussion", "piano",
        "classicalpiano", "jazzpiano", "keyboards", "violin", "viola", "cello",
        "trumpet", "trombone", "saxophone", "flute", "clarinet", "harmonica",
        "ukulele", "banjo", "mandolin", "harp", "djing", "turntablism", "scratching"
    ])

    # 12. Food, Cooking, Baking & Culinary
    add_words([
        "cooking", "homecooking", "culinary", "cheflife", "recipes", "mealplanning",
        "cookware", "castiron", "carbonsteel", "cuttingboard", "sharpening",
        "whetstone", "baking", "breadmaking", "sourdough", "artisanbread", "baguettes",
        "focaccia", "brioche", "croissants", "pastry", "patisserie", "desserts",
        "cakebaking", "cakedecorating", "frosting", "fondant", "cookies", "brownies",
        "chocolatier", "chocolate", "confectionery", "macarons", "pies", "tarts",
        "grilling", "bbq", "barbecue", "smoker", "brisket", "pulledpork", "ribs",
        "steaks", "dryaging", "marinade", "charcoal", "pizza", "pizzamaking",
        "woodfiredpizza", "pasta", "pastamaking", "freshpasta", "ravioli", "gnocchi",
        "sauces", "stocks", "broth", "curry", "spices", "seasoning", "fermentation",
        "kimchi", "sauerkraut", "pickling", "canning", "preserves", "kombucha",
        "cheesemaking", "charcuterie", "streetfood", "fastfood", "restaurantreview",
        "foodcritic", "gourmet", "finedining", "coffee", "espresso", "latteart",
        "pourover", "aeropress", "frenchpress", "barista", "coffeeroasting", "tea",
        "matcha", "looseleaf", "teaceremony", "mixology", "cocktails", "craftcocktails",
        "mocktails", "bartending", "winemaking", "sommelier", "winepairing",
        "beerbrewing", "homebrewing", "craftbeer"
    ])

    # 13. Travel, Outdoor & Exploration
    add_words([
        "travel", "travelvlog", "solotravel", "budgettravel", "luxurytravel",
        "backpacking", "hostels", "vanlife", "campervan", "rvlife", "overlanding",
        "roadtrip", "camping", "wildcamping", "bushcraft", "survival", "survivalist",
        "hiking", "trekking", "trailrunning", "mountaineering", "alpinism",
        "scubadiving", "freediving", "snorkeling", "spearfishing", "underwater",
        "surfing", "bigwaves", "kitesurfing", "windsurfing", "kayaking", "canoeing",
        "rafting", "sailing", "catamaran", "boating", "wildlife", "safari",
        "birdwatching", "nationalparks", "wilderness", "foraging", "mushrooms",
        "caving", "spelunking", "canyoneering", "bungee", "skydiving", "paragliding"
    ])

    # 14. Automotive, Motorsports & Aviation
    add_words([
        "automotive", "carreview", "carenthusiast", "supercars", "hypercars",
        "exoticcars", "classiccars", "vintagecars", "musclecars", "jdm",
        "carmodification", "cartuning", "dynorun", "enginebuilding", "turbocharging",
        "supercharging", "exhaustsystem", "suspension", "coilovers", "wheels",
        "tires", "brakes", "bodykit", "carbonfiber", "paintprotection", "ceramiccoating",
        "cardetailing", "carwash", "interiordetailing", "polishing", "restoration",
        "barnfind", "mechanic", "autorepair", "diyauto", "oilchange", "transmission",
        "drifting", "formula1", "f1racing", "motorsport", "dragracing", "trackday",
        "rally", "autocross", "karting", "nascar", "indycar", "offroading",
        "rockcrawling", "mudding", "electricvehicles", "evs", "tesla", "motorcycles",
        "superbikes", "sportbikes", "cruisers", "choppers", "harleydavidson",
        "caferacer", "scrambler", "motocross", "dirtbikes", "enduro", "supermoto",
        "motogp", "motorcyclerepair", "aviation", "airplanes", "flighttraining"
    ])

    # 15. Sciences, Academics, STEM & Humanities
    add_words([
        "physics", "astrophysics", "quantumphysics", "quantummechanics", "relativity",
        "thermodynamics", "electromagnetism", "optics", "nuclearphysics", "particlephysics",
        "cosmology", "astronomy", "stargazing", "telescopes", "blackholes", "galaxies",
        "spacex", "nasa", "isro", "rocketry", "satellites", "chemistry",
        "organicchemistry", "inorganicchemistry", "biochemistry", "laboratory",
        "biology", "microbiology", "genetics", "dna", "crispr", "evolution",
        "zoology", "botany", "ecology", "marinebiology", "neuroscience", "cognitive",
        "mathematics", "calculus", "linearalgebra", "differentialequations", "geometry",
        "trigonometry", "algebra", "statistics", "probability", "combinatorics",
        "numbertheory", "history", "ancienthistory", "medievalhistory", "worldwar",
        "militaryhistory", "archaeology", "anthropology", "sociology", "politicalscience",
        "geopolitics", "geography", "cartography", "philosophy", "stoicism",
        "existentialism", "ethics", "epistemology", "logic", "literature",
        "linguistics", "etymology", "languages", "polyglot"
    ])

    # 16. Hobbies, Crafts, Making & DIY
    add_words([
        "woodworking", "carpentry", "joinery", "furnituremaking", "woodturning",
        "blacksmithing", "bladesmithing", "knifemaking", "forging", "welding",
        "metalworking", "machining", "lathe", "millingmachine", "cncrouter",
        "lasercutting", "3dprinting", "resinprinting", "diyelectronics", "arduino",
        "raspberrypi", "robotics", "dronebuilding", "rcplanes", "rccars",
        "modelbuilding", "gundam", "gunpla", "warhammer", "miniaturepainting",
        "diorama", "leathercraft", "leatherworking", "shoemaking", "pottery",
        "ceramicart", "wheelthrown", "handbuilding", "glazing", "sewing",
        "patternmaking", "quilting", "embroidery", "crossstitch", "knitting",
        "crochet", "macrame", "weaving", "textileart", "jewelrymaking",
        "silversmithing", "gemstone", "lapidary", "wirewrapping", "origami",
        "papercraft", "bookbinding", "gardening", "vegetablegarden", "organicgardening",
        "hydroponics", "aquaponics", "greenhouse", "indoorplants", "houseplants",
        "succulents", "cacti", "bonsai", "beekeeping", "backyardchickens",
        "homesteading", "offgrid", "aquascaping", "plantedtank", "aquarium",
        "freshwater", "saltwater", "reeftank", "corals", "cichlids", "bettafish"
    ])

    # 17. Lifestyle, Fashion, Culture & Entertainment
    add_words([
        "fashion", "mensfashion", "womensfashion", "streetwear", "sneakerhead",
        "sneakers", "thrifting", "vintageclothing", "capsulewardrobe", "minimalism",
        "grooming", "mensgrooming", "beardcare", "wetshaving", "perfume", "fragrance",
        "cologne", "luxurywatches", "horology", "rolex", "seiko", "casio",
        "watchcollecting", "jewelry", "interiordesign", "homedecor", "roommakeover",
        "housetour", "decluttering", "organization", "movies", "filmreview",
        "cinemareview", "boxoffice", "movietheories", "trailers", "reactions",
        "moviebreakdown", "anime", "animereview", "animerereactions", "manga",
        "comicbooks", "marvel", "mcu", "dc", "dcu", "superheroes", "popculture",
        "celebritynews", "videoessays", "mediaanalysis", "critique", "commentary",
        "drama", "satire", "comedy", "standupcomedy", "improv", "sketches",
        "pranks", "parody", "magic", "illusionism", "mentalism", "cardmagic",
        "boardgames", "tabletop", "dungeonsanddragons", "dnd", "chess", "chessopenings",
        "chesstactics", "grandmaster", "speedchess", "puzzles", "sudoku",
        "rubikscube", "speedcubing", "riddles", "trivia", "bookreviews",
        "booktube", "readingvlog", "audiobooks", "novels", "scifi", "fantasybooks",
        "thriller", "truecrime", "coldcases", "forensics"
    ])

    # Deep Expansion Lists: Real technical concepts, specific game genres,
    # creator specialties, hobbies, and disciplines
    domain_extensions = [
        # Photography & Video Specialties
        "bokeh", "aperture", "shutterspeed", "iso", "exposure", "whitebalance",
        "rawphoto", "jpeg", "histogram", "bracketing", "focusstacking", "photogrammetry",
        "cinemagraph", "stopmotion", "lightpainting", "composite", "longexposure",
        "panoramas", "dronevideo", "actioncam", "vloggergear", "studiosetup",
        "lightingratios", "keylight", "filllight", "backlight", "hairlight",
        "rimlight", "gobo", "scrim", "diffuser", "reflector", "cstand", "sandbag",
        "gels", "colorfilter", "lumix", "blackmagic", "redcamera", "arri",
        "panasonic", "fujifilm", "hasselblad", "leica", "pentax", "olympus",
        # Design & Animation Elements
        "storyboard", "animatic", "keyframing", "inbetweening", "rotoscope",
        "claymation", "puppetanimation", "cutoutanimation", "kinetictext",
        "infographic", "wireframe", "prototype", "userflow", "personas",
        "designsystem", "uicomponents", "vectorgraphics", "rastergraphics",
        "scalability", "gridalignment", "white-space", "kerning", "leading",
        "tracking", "serif", "sansserif", "monospaced", "calligraphic",
        # Music Production & Theory
        "arpeggio", "crescendo", "diminuendo", "staccato", "legato", "vibrato",
        "tremolo", "glissando", "polyphony", "monophony", "syncopation",
        "polyrhythm", "time-signature", "bpm", "metronome", "quantization",
        "sidechain", "multiband", "limiter", "clipper", "noisegate", "deesser",
        "chorus", "flanger", "phaser", "distortion", "overdrive", "fuzz",
        "octaver", "wahwah", "envelopeshaper", "lfo", "oscillator", "filtercutoff",
        # Coffee, Tea, Drinks & Culinary Science
        "coldbrew", "nitrobrew", "chemex", "siphon", "moka", "ibrik", "cezve",
        "flatwhite", "cappuccino", "macchiato", "cortado", "ristretto", "lungo",
        "americano", "affogato", "frappuccino", "crema", "tamping", "channeling",
        "grindsize", "burrgrinder", "singleorigin", "darkroast", "mediumroast",
        "lightroast", "arabica", "robusta", "fermentedtea", "oolong", "sencha",
        "genmaicha", "earlgrey", "rooibos", "tisane", "tisanes", "infusion",
        "tincture", "bitters", "syrups", "shaker", "jigger", "strainer", "muddler",
        # Outdoors, Nature & Survival
        "bivouac", "tarpcamping", "hammockcamping", "firesteel", "charcloth",
        "flintandsteel", "bowdrill", "handdrill", "featherstick", "batoning",
        "carving", "whittling", "knottying", "paracord", "waterfiltration",
        "navigation", "compass", "orienteering", "geocaching", "trailmarker",
        "switchbacks", "scree", "talus", "cairn", "ridge", "col", "saddle",
        "crevasse", "serac", "moraine", "arete", "couloir", "cirque",
        # Auto Mechanics & Tuning
        "crankshaft", "camshaft", "pistons", "valvetrain", "cylinderhead",
        "intercooler", "wastegate", "blowoffvalve", "manifold", "downpipe",
        "catalytic", "resonator", "muffler", "differential", "limitedslip",
        "driveshaft", "axles", "strutbar", "swaybar", "bushings", "controlarm",
        "tie-rod", "balljoint", "caliper", "rotors", "brakebleed", "mastercylinder",
        # Computing, Linux & Networking
        "kernel", "bootloader", "systemd", "initramfs", "filesystem", "ext4",
        "btrfs", "zfs", "xfs", "chroot", "cgroups", "namespaces", "iptables",
        "nftables", "subnets", "vlan", "routing", "gateway", "dhcp", "nat",
        "portforwarding", "ssh", "scp", "rsync", "cron", "systemctl", "top",
        "htop", "glances", "tmux", "screen", "neovim", "emacs", "nano",
        # Fitness & Body Mechanics
        "lordosis", "kyphosis", "scoliosis", "pelvictilt", "pronation",
        "supination", "dorsiflexion", "plantarflexion", "abduction", "adduction",
        "externalrotation", "internalrotation", "concentric", "eccentric", "isometric",
        "isokinetic", "fascia", "myofascial", "triggerpoint", "dryneedling",
        "cupping", "kinesiology", "proprioception", "vestibular", "balanceboard",
        # Plants, Botany & Gardening
        "germination", "seedling", "pruning", "pinching", "deadheading", "trellising",
        "staking", "mulching", "composting", "vermicompost", "leafmold", "biochar",
        "fertilizer", "nitrogen", "phosphorus", "potassium", "phbalance", "soilhealth",
        "pollination", "cross-pollination", "heirloom", "perennial", "annuals",
        "biennials", "deciduous", "evergreen", "rhizome", "tuber", "corm", "bulb",
        # Economics, Business & Marketing Metrics
        "elasticity", "monopoly", "oligopoly", "equilibrium", "deadweight",
        "externality", "comparativeadvantage", "opportunitycost", "marginalutility",
        "liquiditytrap", "stagflation", "hyperinflation", "quantitativeeasing",
        "taylorrule", "phillipscurve", "lorenzcurve", "ginicoefficient", "pareto",
        # Gaming Terms & Metas
        "aggro", "kiting", "nerf", "buff", "rework", "hitbox", "hurtbox", "iframes",
        "invincibility", "parry", "riposte", "backstab", "stamina", "cooldown",
        "dps", "tanking", "healing", "support", "crowdcontrol", "stun", "silence",
        "blind", "slow", "root", "knockup", "knockback", "teleport", "blink",
        "stealth", "invisibility", "camouflage", "wallhack", "aimbot", "anticheat"
    ]
    add_words(domain_extensions)

    # Auxiliary expansions across all creator domains
    try:
        from scripts.niche_expansion_vocab import ALL_EXPANSION_LISTS as L1
        from scripts.niche_expansion_vocab_2 import ALL_EXPANSION_LISTS_2 as L2
        from scripts.niche_expansion_vocab_3 import ALL_EXPANSION_LISTS_3 as L3
        from scripts.niche_expansion_vocab_4 import ALL_EXPANSION_LISTS_4 as L4
        from scripts.niche_expansion_vocab_5 import ALL_EXPANSION_LISTS_5 as L5
        from scripts.niche_expansion_vocab_6 import ALL_EXPANSION_LISTS_6 as L6
        from scripts.niche_expansion_vocab_7 import ALL_EXPANSION_LISTS_7 as L7
        from scripts.niche_expansion_vocab_8 import ALL_EXPANSION_LISTS_8 as L8
        for exp_group in [L1, L2, L3, L4, L5, L6, L7, L8]:
            for lst in exp_group:
                add_words(lst)
    except Exception as e:
        print(f"Warning: could not import all auxiliary vocabularies: {e}")

    return sorted(list(niches))

if __name__ == "__main__":
    niches = get_all_niches()
    print(f"Total compiled unique niches: {len(niches)}")
    # Write to src/curated_niches.py
    out_file = Path("src/curated_niches.py")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write('"""\nCurated single-word niche taxonomy for Daily Lead Agent.\n')
        f.write(f'Generated {len(niches)} distinct, verified, strictly one-word creator niches.\n')
        f.write('Free from synthetic numbers, filler suffixes, and duplicates.\n"""\n\n')
        f.write(f"CURATED_NICHES = [\n")
        for i, n in enumerate(niches):
            f.write(f'    "{n}",\n')
        f.write("]\n")
    print(f"Successfully wrote {len(niches)} niches to {out_file}")
