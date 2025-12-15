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
  // NOTE: submit handler will animate then submit the form normally.
  // Avoid navigating via `location.assign` before form.submit() to preserve POST bodies.
  document.querySelectorAll('form').forEach(function(form){
    form.addEventListener('submit', function(ev){
      // Allow confirm() dialogs to work if present
      // Prevent immediate navigation so we can run the exit animation first
      ev.preventDefault()
      const root = document.getElementById('site-root')
      if(root){
        root.classList.remove('page-enter')
        root.classList.add('page-exit')
      }
      // Submit after a short delay so the animation is visible and the POST body is preserved
      setTimeout(function(){ form.submit() }, 200)
    })
  })

})
