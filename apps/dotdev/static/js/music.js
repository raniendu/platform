/**
 * music.js - Background preview player for Spotify widget.
 * Controls playing, pausing, caching HTML5 audio objects, mutual exclusion,
 * equalizer visualizer, and keyboard accessibility. Gracefully falls back
 * to opening in a new tab if a track does not have a preview URL.
 */

document.addEventListener("DOMContentLoaded", () => {
  const trackItems = document.querySelectorAll(".track-item");
  let currentAudio = null;
  let currentTrackId = null;

  trackItems.forEach((item) => {
    const playBtn = item.querySelector(".track-play-btn");
    const previewUrl = item.getAttribute("data-preview-url");
    const spotifyUrl = item.getAttribute("data-spotify-url");
    const trackId = item.getAttribute("data-track-id");
    const trackTitleLink = item.querySelector(".track-title");
    const artwork = item.querySelector(".track-artwork-container");

    const handleAction = (e) => {
      e.preventDefault();
      e.stopPropagation();

      // Fallback behavior: if no preview URL, open in a new tab
      if (!previewUrl) {
        if (spotifyUrl) {
          window.open(spotifyUrl, "_blank", "noopener,noreferrer");
        }
        return;
      }

      // If clicking the currently playing track
      if (currentTrackId === trackId) {
        if (currentAudio && !currentAudio.paused) {
          pauseTrack(item, currentAudio);
        } else if (currentAudio) {
          playTrack(item, currentAudio);
        }
        return;
      }

      // If clicking a new track, stop the currently playing one first
      if (currentAudio) {
        const activeItem = document.querySelector(`.track-item[data-track-id="${currentTrackId}"]`);
        if (activeItem) {
          pauseTrack(activeItem, currentAudio);
        }
        currentAudio.pause();
        currentAudio = null;
      }

      // Create new audio player for the selected track
      const audio = new Audio(previewUrl);
      currentAudio = audio;
      currentTrackId = trackId;

      audio.addEventListener("ended", () => {
        resetTrackUI(item);
        currentAudio = null;
        currentTrackId = null;
      });

      audio.addEventListener("error", () => {
        console.error("Failed to load audio preview stream.");
        resetTrackUI(item);
        currentAudio = null;
        currentTrackId = null;
      });

      playTrack(item, audio);
    };

    // Click vectors
    if (playBtn) {
      playBtn.addEventListener("click", handleAction);
    }
    if (trackTitleLink) {
      trackTitleLink.addEventListener("click", handleAction);
    }
    if (artwork) {
      artwork.style.cursor = "pointer";
      artwork.addEventListener("click", handleAction);
    }

    // Keyboard trigger
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        handleAction(e);
      }
    });
  });

  function playTrack(item, audio) {
    audio.play()
      .then(() => {
        item.classList.add("playing", "active");
        
        // Show pause icon, hide play icon
        const playIcon = item.querySelector(".play-icon");
        const pauseIcon = item.querySelector(".pause-icon");
        const eqVisualizer = item.querySelector(".eq-visualizer");

        if (playIcon) playIcon.style.display = "none";
        if (pauseIcon) pauseIcon.style.display = "block";
        if (eqVisualizer) eqVisualizer.style.display = "inline-flex";

        // Accessibility updates
        const playBtn = item.querySelector(".track-play-btn");
        const trackTitleEl = item.querySelector(".track-title");
        if (playBtn && trackTitleEl) {
          playBtn.setAttribute("aria-label", `Pause preview of ${trackTitleEl.textContent.trim()}`);
        }
      })
      .catch((error) => {
        console.error("Audio playback error:", error);
        resetTrackUI(item);
      });
  }

  function pauseTrack(item, audio) {
    audio.pause();
    item.classList.remove("playing", "active");

    const playIcon = item.querySelector(".play-icon");
    const pauseIcon = item.querySelector(".pause-icon");
    const eqVisualizer = item.querySelector(".eq-visualizer");

    if (playIcon) playIcon.style.display = "block";
    if (pauseIcon) pauseIcon.style.display = "none";
    if (eqVisualizer) eqVisualizer.style.display = "none";

    const playBtn = item.querySelector(".track-play-btn");
    const trackTitleEl = item.querySelector(".track-title");
    if (playBtn && trackTitleEl) {
      playBtn.setAttribute("aria-label", `Play preview of ${trackTitleEl.textContent.trim()}`);
    }
  }

  function resetTrackUI(item) {
    item.classList.remove("playing", "active");
    const playIcon = item.querySelector(".play-icon");
    const pauseIcon = item.querySelector(".pause-icon");
    const eqVisualizer = item.querySelector(".eq-visualizer");

    if (playIcon) playIcon.style.display = "block";
    if (pauseIcon) pauseIcon.style.display = "none";
    if (eqVisualizer) eqVisualizer.style.display = "none";

    const playBtn = item.querySelector(".track-play-btn");
    const trackTitleEl = item.querySelector(".track-title");
    if (playBtn) {
      const title = trackTitleEl ? trackTitleEl.textContent.trim() : "track";
      playBtn.setAttribute("aria-label", `Play preview of ${title}`);
    }
  }
});
