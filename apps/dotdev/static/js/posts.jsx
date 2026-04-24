const { useEffect, useMemo, useState } = React;

const POSTS_PER_PAGE = 3;

function PostsApp() {
  const initialBundle = window.__POSTS_BUNDLE__ || {
    posts: [],
  };

  const [bundle, setBundle] = useState(initialBundle);
  const [expandedSlug, setExpandedSlug] = useState(null);
  const [page, setPage] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let didCancel = false;
    async function fetchBundle() {
      if (!window.__POSTS_API__) {
        return;
      }
      setLoading(true);
      try {
        const response = await fetch(window.__POSTS_API__);
        if (!response.ok) {
          throw new Error(`Failed to load posts (${response.status})`);
        }
        const data = await response.json();
        if (!didCancel) {
          setBundle(data);
          setError(null);
        }
      } catch (fetchError) {
        if (!didCancel) {
          setError(fetchError.message);
        }
      } finally {
        if (!didCancel) {
          setLoading(false);
        }
      }
    }

    fetchBundle();
    return () => {
      didCancel = true;
    };
  }, []);

  const sortedPosts = useMemo(() => bundle.posts || [], [bundle.posts]);
  const totalPages = useMemo(() => {
    if (!sortedPosts.length) {
      return 1;
    }
    return Math.ceil(sortedPosts.length / POSTS_PER_PAGE);
  }, [sortedPosts]);

  useEffect(() => {
    setPage(0);
    setExpandedSlug(null);
  }, [sortedPosts]);

  useEffect(() => {
    setExpandedSlug((current) => {
      if (!current) {
        return current;
      }
      const pagePosts = sortedPosts.slice(
        page * POSTS_PER_PAGE,
        page * POSTS_PER_PAGE + POSTS_PER_PAGE,
      );
      return pagePosts.some((post) => post.slug === current) ? current : null;
    });
  }, [page, sortedPosts]);

  const pagePosts = useMemo(() => {
    const start = page * POSTS_PER_PAGE;
    return sortedPosts.slice(start, start + POSTS_PER_PAGE);
  }, [page, sortedPosts]);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages - 1));
  }, [totalPages]);

  const handleOlder = () => {
    setPage((current) => Math.min(current + 1, totalPages - 1));
  };

  const handleNewer = () => {
    setPage((current) => Math.max(current - 1, 0));
  };

  const handleToggle = (slug) => {
    setExpandedSlug((current) => (current === slug ? null : slug));
  };

  return (
    <div className="posts-layout">
      <main className="posts-main">
        <header className="posts-header">
          <h1>Posts</h1>
          <p className="posts-subtitle">
            Long-form notes, project diaries, and experiments—captured over time.
          </p>
        </header>

        {error && <div className="posts-error">Warning: {error}</div>}
        {loading && <div className="posts-loading">Loading posts...</div>}

        {!sortedPosts.length && !loading && (
          <div className="posts-empty">
            No posts yet. Drop a markdown file into the <code>posts/</code> folder to get started.
          </div>
        )}

        {sortedPosts.length > 0 && (
          <ul className="posts-list" role="list">
            {pagePosts.map((post) => {
              const isExpanded = expandedSlug === post.slug;
              const contentId = `post-${post.slug}`;
              return (
                <li key={post.slug} className="posts-list-item">
                  <article className={isExpanded ? "post-card expanded" : "post-card"}>
                    <header className="post-card-header">
                      <time dateTime={post.date} className="post-card-date">
                        {post.displayDate}
                      </time>
                      {post.tags?.length ? (
                        <ul className="post-card-tags" role="list">
                          {post.tags.map((tag) => (
                            <li key={tag}>#{tag}</li>
                          ))}
                        </ul>
                      ) : null}
                    </header>

                    <h2 className="post-card-title">{post.title}</h2>

                    {post.excerpt ? (
                      <p className="post-card-excerpt">{post.excerpt}</p>
                    ) : null}

                    <footer className="post-card-footer">
                      <button
                        type="button"
                        className="post-card-toggle"
                        onClick={() => handleToggle(post.slug)}
                        aria-expanded={isExpanded ? "true" : "false"}
                        aria-controls={contentId}
                      >
                        {isExpanded ? "Hide post" : "Read post"}
                        <span aria-hidden="true" className="post-card-icon" />
                      </button>
                    </footer>

                    {isExpanded && (
                      <section
                        id={contentId}
                        className="post-card-content"
                        dangerouslySetInnerHTML={{ __html: post.content }}
                      />
                    )}
                  </article>
                </li>
              );
            })}
          </ul>
        )}

        {sortedPosts.length > 3 && (
          <nav className="posts-pagination" aria-label="Posts pagination">
            <button
              type="button"
              className="posts-pagination-button older"
              onClick={handleOlder}
              disabled={page >= totalPages - 1}
            >
              <span aria-hidden="true">←</span> Older
            </button>
            <button
              type="button"
              className="posts-pagination-button newer"
              onClick={handleNewer}
              disabled={page === 0}
            >
              Newer <span aria-hidden="true">→</span>
            </button>
          </nav>
        )}
      </main>

    </div>
  );
}

const rootElement = document.getElementById("posts-app");
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<PostsApp />);
}
