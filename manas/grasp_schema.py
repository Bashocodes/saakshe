"""manas.grasp_schema — the Brand Pack: the deep extraction structure.

The founder's other product (aikizi) decodes ~120 attributes from a single
image via ten parallel lenses. manas grasps a COMPANY with the same depth:
this module is the predefined, in-depth JSON structure — "we know exactly
which fields we extract, and exactly which questions we can ask."

It is pure data + pure functions (no models, no I/O). The honesty rule is the
same as doubts.py: a field is COVERED only if a real source's text contains
one of its stems; everything else is a genuine gap the founder can be asked
about. Models never invent fields and never invent questions.

  * tier 1 — core: the flywheel decides/makes/engages badly without it
  * tier 2 — enriching: makes the work deeper, never blocks it

  * kind "fact"        → lands as a sourced claim
  * kind "voice_rule"  → lands in voice rules
  * kind "brand_rule"  → lands in brand rules
  * kind "asset"       → lands in the vault (covered iff the vault holds one)
  * kind "channel"     → lands as channel presence

Wired into doubts.py behind SAAKSHE_DEEP_GRASP=1 (default off — the classic
4-dimension flow stays byte-identical until the founder flips the flag).
"""

from __future__ import annotations

import os


def _f(key, label, ask, tier, kind, stems, owned_only=False):
    return {
        "key": key, "label": label, "ask": ask, "tier": tier, "kind": kind,
        "stems": tuple(stems),
        # owned_only fields are never asked about a PUBLIC repository the
        # founder is merely exploring — they only apply to the founder's own.
        "owned_only": owned_only,
    }


SECTIONS = [
    # ── identity ─────────────────────────────────────────────────────────────
    {"key": "identity", "title": "Identity", "fields": [
        _f("name", "company name", "What is the company called, exactly as it should appear?",
           1, "fact", ("name is", "called", "we are", "©", "copyright")),
        _f("one_liner", "one-line what-it-is", "In one line — what is this?",
           1, "fact", ("is a", "is an", "is the", "platform", "app", "tool", "studio", "service")),
        _f("tagline", "tagline", "Is there a tagline — the words under the logo?",
           2, "fact", ("tagline", "slogan", "motto", "—the", "subtitle")),
        _f("elevator_pitch", "elevator pitch", "The 30-second pitch — how is it told to a stranger?",
           2, "fact", ("pitch", "in short", "simply put", "tl;dr", "in a nutshell")),
        _f("category", "category / market", "What category does this live in (e.g. creative tools, wellness, devtools)?",
           1, "fact", ("categor", "market", "industry", "space", "sector", "saas", "b2b", "b2c")),
        _f("stage", "company stage", "What stage are you at — idea, shipped, revenue, funded?",
           2, "fact", ("beta", "launched", "shipped", "founded", "funded", "seed", "revenue", "pre-launch"), owned_only=True),
        _f("founding_story", "founding story", "Why does this exist — the one-paragraph origin story?",
           2, "fact", ("founded", "started", "began", "story", "origin", "why we")),
        _f("mission", "mission", "What is the mission — the change you want in the world?",
           2, "fact", ("mission", "vision", "we believe", "purpose", "exists to")),
        _f("founder_names", "founder name(s)", "Who is behind this — name(s) the public should see?",
           2, "fact", ("founder", "built by", "made by", "created by", "team"), owned_only=True),
        _f("geography", "home geography", "Where is the company based / where is its heart market?",
           2, "fact", ("based in", "headquarter", "india", "usa", "europe", "remote", "global")),
        _f("languages", "operating languages", "Which languages do you operate in?",
           2, "fact", ("english", "hindi", "tamil", "language", "localiz", "multilingual")),
        _f("legal_form", "legal form", "Any legal form worth knowing (LLC, Pvt Ltd, solo)?",
           2, "fact", ("llc", "pvt", "inc", "ltd", "gmbh", "sole", "llp"), owned_only=True),
        _f("name_pronunciation", "name pronunciation", "How is the name pronounced (and any meaning behind it)?",
           2, "fact", ("pronounc", "means", "meaning", "from the sanskrit", "from the tamil", "named after")),
        _f("domains", "domains & handles", "What domains and primary handles does the brand own?",
           2, "fact", (".com", ".ai", ".io", ".in", "domain", "handle"), owned_only=True),
    ]},
    # ── offer ────────────────────────────────────────────────────────────────
    {"key": "offer", "title": "Offer", "fields": [
        _f("products", "product list", "What products/surfaces exist today — name each?",
           1, "fact", ("product", "feature", "app", "api", "platform", "tool", "service")),
        _f("hero_offer", "hero offer", "If the company could only sell ONE thing, what is the hero offer?",
           1, "fact", ("flagship", "hero", "main product", "core offer", "primary")),
        _f("differentiators", "differentiators", "What makes this different — the 2–3 things rivals can't say?",
           1, "fact", ("unlike", "only", "first", "different", "unique", "moat", "advantage")),
        _f("feature_list", "feature inventory", "Which features matter most to users?",
           2, "fact", ("feature", "capabilit", "supports", "lets you", "you can")),
        _f("use_cases", "use cases", "What do people actually USE it for — top use cases?",
           2, "fact", ("use case", "used for", "for teams", "for creators", "workflow", "helps you")),
        _f("integrations", "integrations", "What does it plug into (APIs, platforms, ecosystems)?",
           2, "fact", ("integrat", "plugin", "api", "webhook", "connects to", "works with")),
        _f("platforms_supported", "platforms supported", "Where does it run — web, iOS, Android, desktop?",
           2, "fact", ("ios", "android", "web app", "desktop", "mac", "windows", "browser")),
        _f("roadmap_themes", "roadmap themes", "What is coming next — the public roadmap themes?",
           2, "fact", ("roadmap", "coming soon", "next up", "planned", "upcoming"), owned_only=True),
        _f("service_level", "service / support", "What support or service level do customers get?",
           2, "fact", ("support", "sla", "onboarding", "white glove", "help center")),
        _f("guarantee", "guarantee / promise", "Any guarantee or promise made to customers?",
           2, "fact", ("guarantee", "promise", "money back", "refund", "no questions")),
    ]},
    # ── pricing ──────────────────────────────────────────────────────────────
    {"key": "pricing", "title": "Pricing", "fields": [
        _f("pricing_model", "pricing model", "How does it make money — free, subscription, usage, one-time?",
           1, "fact", ("pric", "subscrib", "free", "paid", "usage-based", "one-time", "license")),
        _f("tiers", "tier names", "What are the tiers called (e.g. Free / Pro / Studio)?",
           1, "fact", ("tier", "plan", "pro ", "premium", "starter", "enterprise")),
        _f("price_points", "price points", "The actual numbers — what does each tier cost?",
           1, "fact", ("$", "₹", "€", "/mo", "per month", "per year", "/yr", "usd", "inr")),
        _f("currency", "billing currency", "Which currency do you bill in?",
           2, "fact", ("usd", "inr", "eur", "currency", "$", "₹", "€")),
        _f("billing_cadence", "billing cadence", "Monthly, annual, both? Any annual discount?",
           2, "fact", ("monthly", "annual", "yearly", "per month", "per year", "cadence")),
        _f("free_tier", "free tier shape", "What does the free tier include — and where does it stop?",
           2, "fact", ("free tier", "free plan", "freemium", "trial", "credits")),
        _f("discounts", "discounts & deals", "Any standing discounts (students, founders, regions)?",
           2, "fact", ("discount", "coupon", "deal", "off ", "promo"), owned_only=True),
        _f("refund_policy", "refund policy", "What is the refund policy?",
           2, "fact", ("refund", "money back", "cancel", "prorat"), owned_only=True),
        _f("unit_economics", "unit economics", "Rough unit economics — what does serving one customer cost?",
           2, "fact", ("margin", "cogs", "unit econ", "cost per", "ltv", "cac"), owned_only=True),
        _f("payment_rails", "payment rails", "How do people pay (Stripe, Razorpay, app stores)?",
           2, "fact", ("stripe", "razorpay", "paypal", "app store", "checkout", "payment"), owned_only=True),
        _f("trial_length", "trial length", "Is there a trial — how long, what unlocks?",
           2, "fact", ("trial", "14 day", "7 day", "30 day", "try free")),
        _f("enterprise_motion", "enterprise motion", "Any enterprise/teams motion — custom pricing, sales calls?",
           2, "fact", ("enterprise", "contact sales", "custom pricing", "teams plan", "volume"), owned_only=True),
    ]},
    # ── audience ─────────────────────────────────────────────────────────────
    {"key": "audience", "title": "Audience", "fields": [
        _f("primary_segment", "primary audience", "Who is this for, first — the primary audience in plain words?",
           1, "fact", ("custom", "user", "audien", "creator", "founder", "team", "buyer", "client")),
        _f("secondary_segments", "secondary segments", "Who else uses it — secondary segments?",
           2, "fact", ("also for", "secondary", "segment", "persona", "agencies", "studios")),
        _f("age_groups", "age groups", "What age range is the core audience?",
           2, "fact", ("age", "18-", "25-", "gen z", "millennial", "young adult")),
        _f("regions", "audience regions", "Where does the audience live — top regions?",
           2, "fact", ("region", "india", "us ", "europe", "global", "worldwide", "asia")),
        _f("pains", "audience pains", "What pain does the audience feel that this removes?",
           1, "fact", ("pain", "problem", "struggle", "frustrat", "hard to", "tired of")),
        _f("desires", "audience desires", "What does the audience WANT (status, speed, beauty, calm)?",
           2, "fact", ("want", "desire", "dream", "aspir", "wish", "love to")),
        _f("objections", "common objections", "What's the most common objection before buying?",
           2, "fact", ("objection", "but ", "concern", "worry", "hesitat", "too expensive"), owned_only=True),
        _f("community_size", "community size", "How big is the current audience/community (any number)?",
           2, "fact", ("follower", "subscriber", "members", "users", "mau", "community of"), owned_only=True),
        _f("notable_users", "notable users", "Any notable users, logos or testimonials to name?",
           2, "fact", ("trusted by", "used by", "testimonial", "case study", "logos")),
        _f("anti_audience", "who it is NOT for", "Who is this explicitly NOT for?",
           2, "fact", ("not for", "isn't for", "anti-", "we don't serve"), owned_only=True),
        _f("audience_language", "audience's words", "What words does the audience itself use for this problem?",
           2, "fact", ("they call", "they say", "in their words", "searches for", "asks for")),
        _f("community_rituals", "community rituals", "Any rituals the community shares (weekly drops, challenges, streaks)?",
           2, "fact", ("ritual", "weekly", "challenge", "streak", "drop", "tradition")),
    ]},
    # ── voice ────────────────────────────────────────────────────────────────
    {"key": "voice", "title": "Voice", "fields": [
        _f("tone_words", "tone in 3 words", "How should the brand sound in ~3 words (e.g. plain, warm, never hypey)?",
           1, "voice_rule", ("voice", "tone", "warm", "plain", "playful", "bold", "minimal", "calm")),
        _f("formality", "formality level", "Formal, casual, or in-between — how would a refund email read?",
           2, "voice_rule", ("formal", "casual", "friendly", "professional", "conversational")),
        _f("humor", "humor stance", "Does the brand joke? How much humor is allowed?",
           2, "voice_rule", ("humor", "funny", "witty", "playful", "serious", "joke")),
        _f("sentence_length", "sentence rhythm", "Short punchy sentences or long flowing ones?",
           2, "voice_rule", ("short sentence", "punchy", "concise", "long-form", "rhythm")),
        _f("signature_phrases", "signature phrases", "Any signature phrases or words the brand always uses?",
           2, "voice_rule", ("signature", "tagline", "slogan", "catchphrase", "we say")),
        _f("taboo_words", "taboo words", "Words/phrases the brand must NEVER use?",
           1, "voice_rule", ("never say", "avoid", "taboo", "banned word", "don't say"), owned_only=True),
        _f("emoji_stance", "emoji stance", "Emojis: never, sparingly, or freely?",
           2, "voice_rule", ("emoji", "😀", "✨", "no emoji")),
        _f("cta_style", "call-to-action style", "How do you ask people to act — soft invite or direct command?",
           2, "voice_rule", ("cta", "call to action", "sign up", "join", "try", "get started")),
        _f("pov", "person & POV", "Do you write as 'we', 'I', or the product's name?",
           2, "voice_rule", ("we ", "i built", "first person", "third person")),
        _f("jargon_level", "jargon level", "How technical can the words get for your audience?",
           2, "voice_rule", ("jargon", "technical", "simple words", "plain english", "accessible")),
        _f("storytelling_stance", "storytelling stance", "Does the brand tell stories or state facts — narrative or plain?",
           2, "voice_rule", ("story", "narrative", "anecdote", "journey", "behind the scenes")),
        _f("reply_style", "reply style", "How does the brand reply to comments/DMs — playful, brief, warm?",
           2, "voice_rule", ("reply", "respond", "comments", "dm", "community management"), owned_only=True),
    ]},
    # ── visual_dna ───────────────────────────────────────────────────────────
    {"key": "visual_dna", "title": "Visual DNA", "fields": [
        _f("palette_primary", "primary palette", "The brand's primary colors — names or hex codes?",
           1, "brand_rule", ("#", "color", "palette", "hue", "rgb(", "hsl(")),
        _f("palette_mode", "palette mode", "Is the palette monochrome, duotone, pastel, neon…?",
           2, "brand_rule", ("monochrom", "duotone", "pastel", "neon", "muted", "vibrant")),
        _f("logo_marks", "logo marks", "Your logo — wordmark, glyph, variants?",
           1, "asset", ("logo", "wordmark", "favicon", "brandmark", "lockup")),
        _f("logo_clearspace", "logo rules", "Any logo rules — clearspace, minimum size, never-do's?",
           2, "brand_rule", ("clearspace", "clear space", "min size", "logo misuse", "logo rules"), owned_only=True),
        _f("typography_display", "display typeface", "What typeface carries headlines?",
           2, "brand_rule", ("font", "typeface", "typography", "serif", "sans", "mono", "grotesk")),
        _f("typography_body", "body typeface", "And body text — which face, what feel?",
           2, "brand_rule", ("body font", "body text", "readable", "text face")),
        _f("photography_style", "photography style", "What does brand photography look like (editorial, candid, studio)?",
           2, "brand_rule", ("photograph", "editorial", "candid", "studio", "85mm", "bokeh", "film")),
        _f("illustration_style", "illustration style", "Any illustration/iconography style?",
           2, "brand_rule", ("illustrat", "icon", "line art", "3d render", "flat design")),
        _f("motion_style", "motion style", "How does the brand MOVE — calm fades, kinetic cuts, none?",
           2, "brand_rule", ("motion", "animation", "transition", "kinetic", "easing")),
        _f("grid_system", "layout grid", "Any layout/grid conventions (brutalist blocks, Swiss grid…)?",
           2, "brand_rule", ("grid", "layout", "brutalis", "swiss", "whitespace", "bauhaus")),
        _f("era_markers", "era markers", "What era does the aesthetic quote (Y2K, 90s print, futurist…)?",
           2, "brand_rule", ("retro", "y2k", "90s", "futurist", "vintage", "era", "nostalgi")),
        _f("regional_aesthetics", "regional aesthetics", "Any regional aesthetic threads (Indian, Japanese, Scandinavian…)?",
           2, "brand_rule", ("indian", "japanese", "scandinav", "korean", "aesthetic", "motif")),
        _f("texture_finish", "texture & finish", "Matte or glossy, grain or clean — the finish of the brand?",
           2, "brand_rule", ("matte", "glossy", "grain", "texture", "paper", "noise")),
        _f("dark_light_stance", "dark/light stance", "Is the brand dark-mode-first, light-first, or both?",
           2, "brand_rule", ("dark mode", "light mode", "dark-first", "theme")),
        _f("color_temperature", "color temperature", "Warm, cool, or neutral — the temperature of the brand's imagery?",
           2, "brand_rule", ("warm tone", "cool tone", "temperature", "golden", "icy", "neutral grade")),
        _f("mood_keywords", "mood keywords", "Five mood words a stranger should feel from the visuals?",
           2, "brand_rule", ("mood", "feel", "vibe", "atmosphere", "emotion")),
        _f("aspect_ratios", "aspect ratios", "Which aspect ratios does the brand live in (9:16, 1:1, 16:9)?",
           2, "brand_rule", ("9:16", "1:1", "16:9", "4:5", "aspect ratio", "vertical", "portrait")),
        _f("watermark_policy", "watermark policy", "Is work watermarked — where and how strong?",
           2, "brand_rule", ("watermark", "credit", "signature mark", "corner mark"), owned_only=True),
    ]},
    # ── channels ─────────────────────────────────────────────────────────────
    {"key": "channels", "title": "Channels", "fields": [
        _f("channel_x", "X presence", "Is the brand on X? Handle and posting rhythm?",
           1, "channel", ("twitter", "x.com", "@", "tweet")),
        _f("channel_instagram", "Instagram presence", "Instagram — handle, grid style, reels cadence?",
           1, "channel", ("instagram", "insta", "reel", "ig ")),
        _f("channel_linkedin", "LinkedIn presence", "LinkedIn — personal page, company page, or both?",
           1, "channel", ("linkedin",)),
        _f("channel_pinterest", "Pinterest presence", "Pinterest — boards, pins, audience?",
           2, "channel", ("pinterest", "pin ")),
        _f("channel_youtube", "YouTube presence", "YouTube — channel, shorts, long-form?",
           2, "channel", ("youtube", "shorts", "subscriber")),
        _f("website", "website", "The primary website/landing URL?",
           1, "channel", ("http", "www.", ".com", ".ai", ".io")),
        _f("newsletter", "newsletter", "Any newsletter/email list — platform and size?",
           2, "channel", ("newsletter", "substack", "email list", "mailing list")),
        _f("blog", "blog / content", "A blog or content hub — where does long-form live?",
           2, "channel", ("blog", "article", "post", "essays", "docs site")),
        _f("community_space", "community space", "Any owned community (Discord, circle, forum)?",
           2, "channel", ("discord", "slack community", "forum", "circle", "telegram")),
        _f("posting_cadence", "posting cadence", "How often does the brand post, realistically?",
           2, "channel", ("daily", "weekly", "cadence", "every day", "per week"), owned_only=True),
        _f("best_channel", "best channel", "Which single channel works BEST today?",
           1, "channel", ("best channel", "most traction", "works best", "main channel"), owned_only=True),
        _f("link_hub", "link hub", "Is there a link-in-bio hub (Linktree or own page)?",
           2, "channel", ("linktree", "link in bio", "links page", "bio.link")),
        _f("social_bio", "social bio line", "The one bio line used across platforms?",
           2, "channel", ("bio", "profile says", "about line")),
        _f("press_kit", "press kit", "Does a press/media kit exist — where?",
           2, "channel", ("press kit", "media kit", "brand kit", "assets page"), owned_only=True),
    ]},
    # ── proof ────────────────────────────────────────────────────────────────
    {"key": "proof", "title": "Proof", "fields": [
        _f("testimonials", "testimonials", "Your 2–3 strongest testimonials (verbatim)?",
           2, "fact", ("testimonial", "“", "review", "5 star", "loved")),
        _f("case_studies", "case studies", "Any case studies or before/afters?",
           2, "fact", ("case study", "before and after", "results", "increased")),
        _f("metrics_public", "public metrics", "Metrics you're willing to say out loud (users, images, uptime)?",
           2, "fact", ("10,000", "100k", "users", "generated", "uptime", "rating"), owned_only=True),
        _f("press", "press & mentions", "Any press, podcasts or notable mentions?",
           2, "fact", ("featured in", "press", "podcast", "interview", "techcrunch")),
        _f("awards", "awards", "Awards, hackathon wins, certifications?",
           2, "fact", ("award", "winner", "hackathon", "certified", "finalist")),
        _f("social_proof_numbers", "social-proof numbers", "Follower/community counts worth citing?",
           2, "fact", ("followers", "subscribers", "members", "stars on github"), owned_only=True),
        _f("ratings", "ratings", "App-store or marketplace ratings worth citing?",
           2, "fact", ("rating", "stars", "4.8", "4.9", "reviews on")),
        _f("github_stars", "github stars", "If open source — stars, forks, contributors?",
           2, "fact", ("stars", "forks", "contributors", "open source", "github.com")),
    ]},
    # ── culture_context ──────────────────────────────────────────────────────
    {"key": "culture_context", "title": "Cultural Context", "fields": [
        _f("cultural_motifs", "cultural motifs", "Recurring cultural motifs in the brand (mythology, craft, music…)?",
           2, "fact", ("motif", "mytholog", "craft", "ritual", "tradition", "sanskrit", "tamil")),
        _f("seasonal_moments", "seasonal moments", "Which seasonal/calendar moments matter (Diwali, launches, summer)?",
           2, "fact", ("diwali", "christmas", "new year", "season", "festival", "launch week")),
        _f("communities_adjacent", "adjacent communities", "Which existing communities/scenes is the brand adjacent to?",
           2, "fact", ("community", "scene", "subculture", "movement", "niche")),
        _f("values_public", "public values", "Values the brand takes a public stand on (and ones it avoids)?",
           2, "fact", ("values", "stand for", "believe in", "ethics", "sustainab"), owned_only=True),
        _f("inspirations", "brand inspirations", "Brands/artists you consider kin or north stars?",
           2, "fact", ("inspired by", "influence", "north star", "kin", "reference"), owned_only=True),
        _f("memes_stance", "memes stance", "Does the brand touch memes/trends, or stay timeless?",
           2, "fact", ("meme", "trend", "viral", "timeless", "evergreen"), owned_only=True),
        _f("holidays_observed", "holidays observed", "Which holidays does the brand mark — and which never?",
           2, "fact", ("holiday", "diwali", "christmas", "eid", "halloween", "independence day"), owned_only=True),
        _f("tone_references", "tone references", "A brand whose TONE (not look) this one echoes?",
           2, "fact", ("sounds like", "tone of", "voice like", "writes like"), owned_only=True),
    ]},
    # ── constraints ──────────────────────────────────────────────────────────
    {"key": "constraints", "title": "Constraints", "fields": [
        _f("compliance_topics", "compliance topics", "Topics needing care (health claims, finance, minors…)?",
           1, "brand_rule", ("compliance", "regulat", "legal", "disclaimer", "hipaa", "gdpr")),
        _f("banned_claims", "banned claims", "Claims you must never make (results, comparisons, numbers)?",
           1, "brand_rule", ("never claim", "banned", "cannot say", "no guarantees", "avoid claiming"), owned_only=True),
        _f("competitors_named", "competitor stance", "May the brand name competitors? Which exist?",
           2, "fact", ("competitor", "alternative", "vs ", "rival", "compared to")),
        _f("partnership_locks", "partnership locks", "Any partnerships/exclusivities that constrain what you say?",
           2, "fact", ("partner", "exclusive", "sponsor", "nda", "agreement"), owned_only=True),
        _f("budget_ceilings", "spend ceilings", "Any hard ceilings on campaign/creative spend?",
           2, "fact", ("budget", "cap", "ceiling", "max spend", "limit"), owned_only=True),
        _f("platform_bans", "platform no-gos", "Platforms or formats the brand refuses to touch?",
           2, "brand_rule", ("never post", "no tiktok", "refuse", "won't use", "no-go"), owned_only=True),
        _f("privacy_stance", "privacy stance", "What is promised about user data and privacy?",
           2, "brand_rule", ("privacy", "data", "gdpr", "we never sell", "encrypted")),
        _f("accessibility_stance", "accessibility stance", "Any accessibility commitments (contrast, captions, alt text)?",
           2, "brand_rule", ("accessib", "a11y", "contrast", "captions", "screen reader")),
    ]},
    # ── seo_discovery ────────────────────────────────────────────────────────
    {"key": "seo_discovery", "title": "SEO & Discovery", "fields": [
        _f("seo_keywords", "seo keywords", "Top 5 search phrases this should rank for?",
           1, "fact", ("seo", "keyword", "rank", "search for", "google for")),
        _f("brand_search_terms", "brand search terms", "What do people type when they look for YOU specifically?",
           2, "fact", ("search term", "typed", "branded search", "navigational"), owned_only=True),
        _f("hashtags", "hashtags", "House hashtags the brand owns or rides?",
           2, "channel", ("#", "hashtag")),
        _f("alt_text_style", "alt-text style", "How is image alt text written — plain, poetic, keyworded?",
           2, "brand_rule", ("alt text", "alt=", "image description")),
        _f("app_store_listing", "app-store listing", "Is there an app-store presence — which stores, what title?",
           2, "channel", ("app store", "play store", "testflight", "appstore")),
        _f("directory_listings", "directory listings", "Listed anywhere that matters (Product Hunt, G2, MJ showcase)?",
           2, "channel", ("product hunt", "g2", "capterra", "showcase", "directory")),
        _f("backlink_sources", "backlink sources", "Who links to this — notable backlink sources?",
           2, "fact", ("featured", "linked", "backlink", "referral", "press")),
        _f("github_topics", "github topics", "If open source — repo topics/tags chosen?",
           2, "fact", ("topics", "tags", "awesome list", "repository")),
    ]},
]


# ─── Pure helpers ────────────────────────────────────────────────────────────
def all_fields() -> list[dict]:
    return [f for s in SECTIONS for f in s["fields"]]


def tier1_fields() -> list[dict]:
    return [f for f in all_fields() if f["tier"] == 1]


def field_count() -> int:
    return len(all_fields())


def enabled() -> bool:
    """Deep grasp is opt-in: SAAKSHE_DEEP_GRASP=1. Default off keeps the
    classic 4-dimension doubt flow byte-identical."""
    return os.environ.get("SAAKSHE_DEEP_GRASP", "") == "1"


def _covered(field: dict, corpus: str, has_logo: bool) -> bool:
    if field["kind"] == "asset":
        return has_logo
    return any(stem in corpus for stem in field["stems"])


def missing_fields(corpus_text: str, *, has_logo: bool = False,
                   owned: bool = True, tier: int | None = None) -> list[dict]:
    """Every schema field NOT evidenced in the imbibed corpus. Public repos
    (owned=False) skip owned_only fields entirely — you don't ask a repo the
    founder is exploring where its founder keeps the logo."""
    corpus = (corpus_text or "").lower()
    out = []
    for f in all_fields():
        if tier is not None and f["tier"] != tier:
            continue
        if not owned and (f["owned_only"] or f["kind"] == "asset"):
            continue
        if not _covered(f, corpus, has_logo):
            out.append(f)
    return out


def coverage(corpus_text: str, *, has_logo: bool = False,
             owned: bool = True) -> dict[str, dict]:
    """Per-section {covered, total} — the cockpit's pressure board: every
    section always visible, lit only by real evidence."""
    corpus = (corpus_text or "").lower()
    out: dict[str, dict] = {}
    for s in SECTIONS:
        fields = [f for f in s["fields"]
                  if owned or not (f["owned_only"] or f["kind"] == "asset")]
        covered = sum(1 for f in fields if _covered(f, corpus, has_logo))
        out[s["key"]] = {"title": s["title"], "covered": covered, "total": len(fields)}
    return out
