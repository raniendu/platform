document.addEventListener('DOMContentLoaded', () => {
  const timeline = document.getElementById('posts-timeline');
  if (!timeline) return;

  const items = Array.from(timeline.querySelectorAll('.timeline-item'));
  const buttons = Array.from(document.querySelectorAll('.filter-button'));
  const emptyMessage = document.getElementById('posts-empty-message');
  const initialTag = timeline.dataset.selectedTag || '';

  const setActiveTag = (tag) => {
    buttons.forEach((button) => {
      const isActive = (button.dataset.tag || '') === tag;
      button.setAttribute('aria-pressed', String(isActive));
    });

    let visibleCount = 0;
    items.forEach((item) => {
      const tags = (item.dataset.tags || '').split(' ').filter(Boolean);
      const matches = !tag || tags.includes(tag);
      item.hidden = !matches;
      if (matches) {
        visibleCount += 1;
      }
    });

    if (emptyMessage) {
      emptyMessage.hidden = visibleCount !== 0;
    }

    if (window.history && window.location) {
      const url = new URL(window.location.href);
      if (tag) {
        url.searchParams.set('tag', tag);
      } else {
        url.searchParams.delete('tag');
      }
      window.history.replaceState({}, '', url);
    }
  };

  buttons.forEach((button) => {
    button.addEventListener('click', () => {
      const nextTag = button.dataset.tag || '';
      setActiveTag(nextTag);
    });
  });

  setActiveTag(initialTag);
});
