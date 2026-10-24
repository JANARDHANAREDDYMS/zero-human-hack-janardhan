Stage: intake_extract. Input: submission with product_id, natural-language text, and optionally a research_question. Output: the minimal intake schema.

Preserve product_id exactly and set schema_version to 2.0. Describe only the product, capabilities, and limitations actually supplied. Extract name, category, price, audience, market, and known features only when stated; otherwise omit or use null as allowed by the schema. An uncertain audience is not permission to invent an authoritative target market. Do not fill in a typical price, battery life, dimension, country, or promised benefit from your background knowledge.

Use the explicitly supplied research_question if present. Otherwise extract a clear question from the text. If none exists, use: "Explore potential customer needs and alternatives." This is an exploratory default, not a client claim. Research is allowed to proceed with an incomplete offer; unknown specifications are not failures.

Do not create customers, source records, segment names, competitive conclusions, or a product winner in this stage. No model-generated content may claim to be supplied customer research.
