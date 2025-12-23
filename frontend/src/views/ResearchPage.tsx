/**
 * Research Page
 *
 * Article listing page showing research articles chronologically.
 * Similar to a blog listing page.
 */

import React from 'react';
import { FileText, Calendar, Tag, ArrowRight, BookOpen } from 'lucide-react';
import { articles } from '@/data/articles';
import { InternalPageHeader, PageId } from '@/components/common/PageNavigation';

interface ResearchPageProps {
  onNavigate: (page: PageId) => void;
  onSelectArticle: (articleId: string) => void;
}

export function ResearchPage({ onNavigate, onSelectArticle }: ResearchPageProps) {
  // Sort articles by date (newest first)
  const sortedArticles = [...articles].sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header with Navigation */}
      <InternalPageHeader
        currentPage="research"
        breadcrumbs={[{ label: 'Research' }]}
        onNavigate={onNavigate}
      />

      {/* Hero Section */}
      <section className="pt-28 pb-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <BookOpen className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1
                className="text-4xl md:text-5xl"
                style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
              >
                Research
              </h1>
              <p className="text-indigo-400 text-sm font-medium mt-1">
                Symbol-μ Technical Articles
              </p>
            </div>
          </div>
          <p className="text-xl text-gray-400 max-w-2xl">
            Explore the technical foundations, architecture, and capabilities of the
            Symbol-μ cognitive intelligence framework.
          </p>
        </div>
      </section>

      {/* Articles List */}
      <section className="pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="space-y-6">
            {sortedArticles.map((article, index) => (
              <article
                key={article.id}
                className="group relative bg-white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 hover:border-indigo-500/30 transition-all cursor-pointer"
                onClick={() => onSelectArticle(article.id)}
              >
                {/* Article Number */}
                <div className="absolute -left-3 top-6 w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                  <span className="text-xs text-indigo-400 font-medium">
                    {sortedArticles.length - index}
                  </span>
                </div>

                <div className="flex items-start justify-between gap-6">
                  <div className="flex-1">
                    {/* Title */}
                    <h2
                      className="text-xl text-white mb-2 group-hover:text-indigo-300 transition-colors"
                      style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
                    >
                      {article.title}
                    </h2>

                    {/* Short Description */}
                    <p className="text-gray-400 mb-4 leading-relaxed">
                      {article.shortDescription}
                    </p>

                    {/* Meta Info */}
                    <div className="flex items-center gap-4 text-sm">
                      <div className="flex items-center gap-1.5 text-gray-500">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>{formatDate(article.publishedAt)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {article.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 text-xs"
                          >
                            <Tag className="w-2.5 h-2.5" />
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Arrow */}
                  <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-white/5 group-hover:bg-indigo-500/20 transition-colors">
                    <ArrowRight className="w-5 h-5 text-gray-500 group-hover:text-indigo-400 transition-colors" />
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="text-lg text-gray-500"
              style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
            >
              Symbol-μ
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500 text-sm">Research</span>
          </div>
          <div className="text-gray-600 text-xs">
            {articles.length} articles published
          </div>
        </div>
      </footer>
    </div>
  );
}
