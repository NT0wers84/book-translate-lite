## Genre: game fiction (LitRPG, GameLit, system/stat-based stories)

- **System text** (notifications, messages, achievements, stat blocks, menus): keep each as its own paragraph with the same bold/italic/block formatting. Its wording is formulaic: render each fixed formula once and reuse it identically (“New Achievement!”, “Reward:”, “Level up!”), adding it to META.new_entities.
- **Skills, spells, classes, items, boxes, titles**: translated with Initial Capitals where {language} allows, and kept identical every time they recur; put each one in META.new_entities.
- **Stats and numbers**: digits, the same format everywhere (“+5 Strength”, “Level 12”), {language} number separators.
- **Gamer jargon** (loot, boss, quest, party, buff, level up…): keep in English the words {language} players actually use in English; translate the others; decide once and keep it.
- **Chat lines** `Name: text`: no quotation marks; a character who types in capitals keeps typing in capitals (list them in project.json `uppercase_chat`).
- In-world documents (journals, guides, notes by earlier characters): keep their heading format identical every time.
