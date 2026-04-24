document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('image-modal');
  const modalImg = document.getElementById('modal-image');
  const closeBtn = document.querySelector('.modal-close');

  // Metadata elements
  const modalLocation = document.getElementById('modal-location');
  const modalDate = document.getElementById('modal-date');
  const modalCaption = document.getElementById('modal-caption');

  if (!modal || !modalImg || !closeBtn) return;

  function openModal(img) {
    modalImg.src = img.src;
    modalImg.alt = img.alt || '';

    // Update metadata
    if (modalLocation) modalLocation.textContent = img.dataset.location || '';
    if (modalDate) modalDate.textContent = img.dataset.date || '';

    // Use caption if available, fallback to title, then alt
    const captionText = img.dataset.caption || img.dataset.title || img.alt || '';
    if (modalCaption) modalCaption.textContent = captionText;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden'; // Prevent scrolling
  }

  function closeModal() {
    modal.classList.remove('active');
    document.body.style.overflow = '';
    // Clear src to stop loading/playing if it were a video, 
    // and to prevent flash of old image on next open
    setTimeout(() => {
      modalImg.src = '';
      modalImg.alt = '';
      if (modalLocation) modalLocation.textContent = '';
      if (modalDate) modalDate.textContent = '';
      if (modalCaption) modalCaption.textContent = '';
    }, 300); // Wait for transition

    // Remove query param
    const url = new URL(window.location);
    url.searchParams.delete('photo');
    window.history.replaceState({}, '', url);
  }

  // Event delegation for gallery images
  document.addEventListener('click', (e) => {
    const img = e.target.closest('.gallery-item img');
    if (img) {
      openModal(img);
    }
  });

  // Close events
  closeBtn.addEventListener('click', closeModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal || e.target.classList.contains('modal-content')) {
      closeModal();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      closeModal();
    }
  });

  // Check URL query params on load
  const params = new URLSearchParams(window.location.search);
  const photoParam = params.get('photo');
  if (photoParam) {
    // The photo param might be a relative path from the static folder or a full URL.
    // We need to find the matching image on the page to get the full src if possible,
    // or construct it.
    // Let's try to find an image with this src ending.
    const images = document.querySelectorAll('.gallery-item img');
    for (const img of images) {
      if (img.src.endsWith(photoParam) || img.getAttribute('src').endsWith(photoParam)) {
        openModal(img);
        break;
      }
    }
  }
});
