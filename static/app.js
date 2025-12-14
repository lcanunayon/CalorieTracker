// Lightweight page transition: fade out then navigate
document.addEventListener('DOMContentLoaded', function(){
  function attachLinks(){
    document.querySelectorAll('a.nav-link, a.btn, a.brand a').forEach(function(a){
      // only intercept same-origin GET links
      if(!a.href) return
      const url = new URL(a.href, location.href)
      if(url.origin !== location.origin) return
      a.addEventListener('click', function(ev){
        // allow modifiers
        if(ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.altKey) return
        ev.preventDefault()
        const root = document.getElementById('site-root')
        if(root){
          root.classList.remove('page-enter')
          root.classList.add('page-exit')
        }
        setTimeout(function(){ location.assign(url.href) }, 220)
      })
    })
  }
  attachLinks()
  // Re-attach after partial page updates if needed
})
