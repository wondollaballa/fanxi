import { Newspaper, RefreshCw } from "lucide-react";
import type { NewsItem, PublicView } from "../types";
import { prettyDate } from "../lib/format";
import { Button, Card, EmptyState } from "./ui";

export function NewsPage({
  publicView,
  onRefresh,
}: {
  publicView: PublicView;
  onRefresh: () => void;
}) {
  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">From the world</div>
          <h1 className="page-title">News</h1>
          <p className="page-subtitle">Announcements published by your server administrator.</p>
        </div>
        <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={onRefresh}>
          Refresh
        </Button>
      </div>

      {publicView.news.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Newspaper size={24} />}
            title="No news yet"
            body="When the server administrator publishes an announcement it will appear here."
          />
        </Card>
      ) : (
        <div className="news-list">
          {publicView.news.map((post: NewsItem) => (
            <Card key={post.slug ?? post.title} className="news-article">
              <div className="news-article-head">
                <h2>{post.title}</h2>
                <span>{prettyDate(post.published_at)}</span>
              </div>
              {post.body && <div className="news-body">{post.body}</div>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
