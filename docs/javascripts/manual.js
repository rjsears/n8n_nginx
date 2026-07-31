// Lightbox: click any screenshot in the manual to view it full-screen.
// Click the overlay (or press Escape) to close.

(function () {
  function attachLightbox() {
    document.querySelectorAll('.md-content article img').forEach((img) => {
      // Skip badges and shields
      if (img.src.includes('img.shields.io') || img.src.includes('badge')) return;
      if (img.dataset.lightboxAttached) return;
      img.dataset.lightboxAttached = '1';
      img.addEventListener('click', (e) => {
        e.preventDefault();
        const overlay = document.createElement('div');
        overlay.className = 'lightbox-overlay';
        const big = document.createElement('img');
        big.src = img.src;
        big.alt = img.alt || '';
        overlay.appendChild(big);
        overlay.addEventListener('click', () => overlay.remove());
        const escHandler = (ev) => {
          if (ev.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
          }
        };
        document.addEventListener('keydown', escHandler);
        document.body.appendChild(overlay);
      });
    });
  }

  // Run on initial load and after Material's instant-navigation page swaps
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachLightbox);
  } else {
    attachLightbox();
  }
  // Material instant navigation fires a custom event after page swap
  if (typeof document$ !== 'undefined' && document$.subscribe) {
    document$.subscribe(attachLightbox);
  }
})();
