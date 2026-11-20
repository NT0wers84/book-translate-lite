-- Paragraphs made only of bold text (system messages, notifications) → <div class="system">
local function only_bold(p)
  local ok = false
  for _, el in ipairs(p.content) do
    if el.t == 'Strong' then ok = true
    elseif el.t ~= 'Space' and el.t ~= 'SoftBreak' and el.t ~= 'LineBreak' then return false end
  end
  return ok
end

function Blocks(blocks)
  local out, buf = {}, {}
  local function flush()
    if #buf > 0 then out[#out + 1] = pandoc.Div(buf, {class = 'system'}); buf = {} end
  end
  for _, b in ipairs(blocks) do
    if b.t == 'Para' and only_bold(b) then buf[#buf + 1] = b
    else flush(); out[#out + 1] = b end
  end
  flush()
  return out
end
