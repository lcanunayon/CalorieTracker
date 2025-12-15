// Lightweight page transition: fade out then navigate
document.addEventListener('DOMContentLoaded', function(){
  function animateAndNavigate(url){
    const root = document.getElementById('site-root')
    if(root){
      root.classList.remove('page-enter')
      root.classList.add('page-exit')
    }
    setTimeout(function(){ location.assign(url) }, 220)
  }

  // Intercept same-origin link clicks for smooth transitions
  document.querySelectorAll('a.nav-link, a.btn, a.brand a').forEach(function(a){
    if(!a.href) return
    const url = new URL(a.href, location.href)
    if(url.origin !== location.origin) return
    a.addEventListener('click', function(ev){
      if(ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.altKey) return
      ev.preventDefault()
      animateAndNavigate(url.href)
    })
  })

  // Intercept form submissions to animate before submit
  document.querySelectorAll('form').forEach(function(form){
    form.addEventListener('submit', function(ev){
      // For destructive actions (delete) allow confirm to run
      // Let the form submit normally but animate
      const action = form.getAttribute('action') || location.href
      ev.preventDefault()
      // small timeout to allow any confirm dialog to resolve
      setTimeout(function(){
        animateAndNavigate(action)
        // submit after navigation delay to allow server to handle
        setTimeout(function(){ form.submit() }, 240)
      }, 10)
    })
  })

})
