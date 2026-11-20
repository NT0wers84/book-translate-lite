-- Paragrafi fatti solo di grassetto (messaggi di sistema, notifiche) → <div class="sistema">
local function solo_grassetto(p)
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
    if #buf > 0 then out[#out + 1] = pandoc.Div(buf, {class = 'sistema'}); buf = {} end
  end
  for _, b in ipairs(blocks) do
    if b.t == 'Para' and solo_grassetto(b) then buf[#buf + 1] = b
    else flush(); out[#out + 1] = b end
  end
  flush()
  return out
end
