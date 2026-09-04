const menuButton = document.querySelector('.menu-btn');
const header = document.querySelector('.nav');

menuButton.addEventListener('click', () => {
  const open = header.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
});

document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => {
  header.classList.remove('open');
  menuButton.setAttribute('aria-expanded', 'false');
}));

// Highlight the navigation item for the section currently in view.
const sectionLinks = [...document.querySelectorAll('nav a[href^="#"]')];
const observedSections = sectionLinks
  .map(link => document.querySelector(link.getAttribute('href')))
  .filter(Boolean);

if ('IntersectionObserver' in window) {
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      sectionLinks.forEach(link => {
        link.classList.toggle('is-active', link.getAttribute('href') === `#${entry.target.id}`);
      });
    });
  }, {rootMargin: '-30% 0px -60% 0px'});
  observedSections.forEach(section => sectionObserver.observe(section));
}

document.getElementById('year').textContent = new Date().getFullYear();

// Send quote submissions without leaving the website.
(function(){
  const form = document.getElementById('quote-form');
  const statusEl = document.getElementById('quote-status');
  if (!form) return;

  function showStatus(message, type) {
    statusEl.textContent = message;
    statusEl.className = `quote-status is-visible is-${type}`;
  }

  form.querySelectorAll('[required]').forEach((field) => {
    field.addEventListener('invalid', () => {
      showStatus('Please complete all required fields marked with *.', 'error');
    });
    field.addEventListener('input', () => {
      if (form.checkValidity()) statusEl.className = 'quote-status';
    });
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const originalLabel = button.innerHTML;
    button.disabled = true;
    button.textContent = 'Sending…';
    showStatus('Sending your enquiry securely…', 'sending');

    const payload = Object.fromEntries(new FormData(form).entries());
    payload._replyto = payload.email || '';

    try {
      if (window.location.protocol === 'file:') throw new Error('SERVER_REQUIRED');
      payload._subject = `New Quote: ${payload.pickup} to ${payload.destination} — ${payload.from_name}`;
      payload._template = 'table';
      const response = await fetch('https://formsubmit.co/ajax/krishnatemo931@gmail.com', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify(payload)
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.success === false || result.success === 'false') {
        const error = new Error(result.message || 'Email request failed');
        error.code = 'API_ERROR';
        throw error;
      }
      showStatus('✓ Thank you! Your enquiry has been sent successfully. We will contact you shortly.', 'success');
      form.reset();
      form.dispatchEvent(new CustomEvent('quote:sent'));
    } catch (error) {
      console.error('Quote form error:', error);
      let message = 'We could not connect to the email server. Open http://localhost:8000 and try again.';
      if (error.message === 'SERVER_REQUIRED') {
        message = 'Please open http://localhost:8000 instead of opening the HTML file directly.';
      } else if (error.code === 'API_ERROR') {
        message = error.message;
      }
      showStatus(message, 'error');
    } finally {
      button.disabled = false;
      button.innerHTML = originalLabel;
    }
  });
})();

// Modal open/close behaviour for the quote form
(function(){
  const modal = document.getElementById('quote-modal');
  if (!modal) return;
  const openBtns = document.querySelectorAll('.open-quote');
  const closeBtn = modal.querySelector('.modal-close');
  const overlay = modal.querySelector('.modal-overlay');
  const form = document.getElementById('quote-form');
  let lastFocused = null;

  function openModal(){
    lastFocused = document.activeElement;
    modal.classList.add('is-visible');
    modal.setAttribute('aria-hidden','false');
    document.body.style.overflow = 'hidden';
    const first = modal.querySelector('input,select,textarea');
    if (first) first.focus();
  }
  function closeModal(){
    modal.classList.remove('is-visible');
    modal.setAttribute('aria-hidden','true');
    document.body.style.overflow = '';
    if (lastFocused) lastFocused.focus();
    const status = document.getElementById('quote-status');
    if (status) {
      status.textContent = '';
      status.className = 'quote-status';
    }
  }

  openBtns.forEach(b => b.addEventListener('click', (e)=>{ e.preventDefault(); openModal(); }));
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (overlay) overlay.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape' && modal.classList.contains('is-visible')) closeModal(); });

  if (form) {
    form.addEventListener('quote:sent', () => {
      window.setTimeout(closeModal, 2500);
    });
  }

})();
