
HOVER_CSS = '.__pyweb_hover__ { outline: 2px solid #33aaff !important; outline-offset: -2px; }'

# Build a JS string with the CSS embedded safely.
HOVER_JS = (
    "(() => {"
    "  const styleId='__pyweb_hover_style__';"
    "  if (!document.getElementById(styleId)) {"
    "    const st = document.createElement('style'); st.id=styleId; st.textContent='.__pyweb_hover__ { outline: 2px solid #33aaff !important; outline-offset: -2px; }'; document.documentElement.appendChild(st);"
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
)

SIBLING_IMAGES_JS = (
    "(el => {"
    "  const container = el.closest('*');"
    "  if (!container) return [];"
    "  let p = el.parentElement; let chosen = null;"
    "  while (p) {"
    "    const sibs = p.parentElement ? [...p.parentElement.children].filter(c => c.tagName===p.tagName && c.className===p.className) : [];"
    "    if (sibs.length >= 2) { chosen = p.parentElement; break; }"
    "    p = p.parentElement;"
    "  }"
    "  const scope = chosen || document.body;"
    "  return [...scope.querySelectorAll('img')].map(i => i.currentSrc || i.src).filter(Boolean);"
    "})(arguments[0]);"
)
