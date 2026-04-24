(function () {
  var THEME_KEY = 'theme';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {
    var root = document.documentElement;
    var themeToggle = document.getElementById('theme-toggle');
    var menuToggle = document.getElementById('menu-toggle');
    var primaryNav = document.querySelector('nav[aria-label="Primary"]');

    var currentTheme = root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';

    function applyTheme(mode) {
      var next = mode === 'dark' ? 'dark' : 'light';

      if (next === 'dark') {
        root.setAttribute('data-theme', 'dark');
        if (themeToggle) themeToggle.setAttribute('aria-pressed', 'true');
      } else {
        root.removeAttribute('data-theme');
        if (themeToggle) themeToggle.setAttribute('aria-pressed', 'false');
      }

      if (currentTheme !== next) {
        currentTheme = next;
        try {
          document.dispatchEvent(
            new CustomEvent('themechange', { detail: { theme: next } })
          );
        } catch (error) {}
      }
    }

    function getStoredTheme() {
      try {
        var saved = localStorage.getItem(THEME_KEY);
        if (saved === 'dark' || saved === 'light') {
          return saved;
        }
      } catch (error) {}
      return 'light';
    }

    function persistTheme(mode) {
      try {
        localStorage.setItem(THEME_KEY, mode);
      } catch (error) {}
    }

    function toggleMenu(force) {
      if (!menuToggle || !primaryNav) return;
      var isOpen = typeof force === 'boolean' ? force : !primaryNav.classList.contains('is-open');
      primaryNav.classList.toggle('is-open', isOpen);
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      if (isOpen) {
        menuToggle.classList.add('is-open');
        var firstLink = primaryNav.querySelector('a');
        if (firstLink) firstLink.focus();
      } else {
        menuToggle.classList.remove('is-open');
      }
    }

    var initialTheme = root.getAttribute('data-theme') === 'dark' ? 'dark' : getStoredTheme();
    applyTheme(initialTheme);

    if (themeToggle) {
      themeToggle.addEventListener('click', function () {
        var isDark = root.getAttribute('data-theme') === 'dark';
        var next = isDark ? 'light' : 'dark';
        var previous = currentTheme;
        applyTheme(next);
        if (previous !== currentTheme) {
          persistTheme(next);
        }
      });
    }

    if (menuToggle && primaryNav) {
      menuToggle.addEventListener('click', function () {
        toggleMenu();
      });

      primaryNav.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', function () {
          toggleMenu(false);
        });
      });

      document.addEventListener('click', function (event) {
        if (!primaryNav.contains(event.target) && !menuToggle.contains(event.target)) {
          toggleMenu(false);
        }
      });

      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          toggleMenu(false);
          menuToggle.focus();
        }
      });

      window.addEventListener('resize', function () {
        if (window.innerWidth > 768) {
          toggleMenu(false);
        }
      });
    }

    // Email reveal functionality
    function initEmailReveal() {
      try {
        // Use event delegation to handle clicks on email reveal buttons
        document.addEventListener('click', function(event) {
          var target = event.target;
          if (target.matches('.email-reveal-button') || 
              target.closest('.email-reveal-button')) {
            event.preventDefault();
            var button = target.matches('.email-reveal-button') ? 
                        target : target.closest('.email-reveal-button');
            var container = button.closest('.email-reveal');
            if (container) {
              toggleEmailReveal(container);
            }
          }
        });

        // Add keyboard navigation support
        document.addEventListener('keydown', function(event) {
          var target = event.target;
          if ((event.key === 'Enter' || event.key === ' ') && 
              (target.matches('.email-reveal-button') || 
               target.closest('.email-reveal-button'))) {
            event.preventDefault();
            var button = target.matches('.email-reveal-button') ? 
                        target : target.closest('.email-reveal-button');
            var container = button.closest('.email-reveal');
            if (container) {
              toggleEmailReveal(container);
            }
          }
        });
      } catch (error) {
        // Silently handle any initialization errors
        console.warn('Email reveal initialization failed:', error);
      }
    }

    function toggleEmailReveal(container) {
      try {
        if (!container) return;
        
        var button = container.querySelector('.email-reveal-button');
        var placeholder = container.querySelector('.email-placeholder');
        var address = container.querySelector('.email-address');
        var email = container.dataset.email;
        
        if (!button || !placeholder || !address || !email) return;
        
        // Check if email is already revealed
        if (address.hidden) {
          // Create mailto link
          var link = document.createElement('a');
          link.href = 'mailto:' + email;
          link.textContent = email;
          link.className = 'email-link';
          link.setAttribute('aria-label', 'Send email to ' + email);
          
          // Replace the entire button with the mailto link
          container.replaceChild(link, button);
        }
      } catch (error) {
        console.warn('Email reveal toggle failed:', error);
      }
    }

    // Initialize email reveal functionality
    initEmailReveal();
  });
})();
