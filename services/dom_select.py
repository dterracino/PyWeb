
HOVER_CSS = ".__pyweb_hover__ { outline: 2px solid #33aaff !important; outline-offset: -2px; }"

# JS to enable hover-outline and click-to-pick; posts {type:'pyweb/elementPicked', info}
HOVER_JS = (
    "(() => {"
    "  const styleId='__pyweb_hover_style__';"
    "  if (!document.getElementById(styleId)) {"
    "    const st = document.createElement('style'); st.id=styleId; st.textContent=%r; document.documentElement.appendChild(st);"
    "  }"
    "  let last;"
    "  const over = e => { const t=e.target; if(last&&last!==t) last.classList.remove('__pyweb_hover__'); t.classList.add('__pyweb_hover__'); last=t; };"
    "  const out = e => { e.target.classList.remove('__pyweb_hover__'); };"
    "  const click = e => {"
    "    e.preventDefault(); e.stopPropagation();"
    "    const el = e.target;"
    "    const info = { tag: el.tagName, id: el.id, classes: [...el.classList], src: el.src||null, outerHTML: el.outerHTML.slice(0,1000) };"
    "    if (window.chrome && window.chrome.webview) { window.chrome.webview.postMessage({ type:'pyweb/elementPicked', info }); }"
    "    remove();"
    "  };"
    "  function remove(){ document.removeEventListener('mouseover', over, true); document.removeEventListener('mouseout', out, true); document.removeEventListener('click', click, true); if(last) last.classList.remove('__pyweb_hover__'); }"
    "  document.addEventListener('mouseover', over, true);"
    "  document.addEventListener('mouseout', out, true);"
    "  document.addEventListener('click', click, true);"
    "  return true;"
    "})();"
) % HOVER_CSS

# Function expression: pass an element; returns a unique list of absolute URLs for sibling-scope images.
SIBLING_IMAGES_JS = (
    "(el => {"
    "  function repeatedScope(n){"
    "    let p = n && n.parentElement, chosen = null;"
    "    while (p) {"
    "      const sibs = p.parentElement ? Array.from(p.parentElement.children).filter(c => c.tagName===p.tagName && c.className===p.className) : [];"
    "      if (sibs.length >= 2) { chosen = p.parentElement; break; }"
    "      p = p.parentElement;"
    "    }"
    "    return chosen || document.body;"
    "  }"
    "  const scope = repeatedScope(el || document.querySelector('img'));"
    "  const urls = Array.from(scope.querySelectorAll('img'))"
    "    .filter(i => i.offsetParent !== null) /* visible only */"
    "    .map(i => i.currentSrc || i.src)"
    "    .filter(Boolean)"
    "    .map(u => { try { return new URL(u, location.href).href } catch (e) { return u } });"
    "  return Array.from(new Set(urls));"
    "})"
)
