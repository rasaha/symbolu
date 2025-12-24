/**
 * Article Page
 *
 * Individual article view with full content.
 * Shows title in bold, short description, separator, and main content.
 * Includes "Article list" link on the right.
 */

import React from 'react';
import { Calendar, Tag, List, ArrowLeft, User } from 'lucide-react';
import { getArticleById, Article } from '@/data/articles';
import { InternalPageHeader, PageId } from '@/components/common/PageNavigation';

interface ArticlePageProps {
  articleId: string;
  onNavigate: (page: PageId) => void;
  onBackToList: () => void;
}

export function ArticlePage({ articleId, onNavigate, onBackToList }: ArticlePageProps) {
  const article = getArticleById(articleId);

  if (!article) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Article not found</h1>
          <button
            onClick={onBackToList}
            className="text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Back to Research
          </button>
        </div>
      </div>
    );
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // Simple markdown-like rendering for content
  const renderContent = (content: string) => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let currentParagraph: string[] = [];

    const flushParagraph = () => {
      if (currentParagraph.length > 0) {
        elements.push(
          <p key={elements.length} className="text-gray-300 leading-relaxed mb-4">
            {currentParagraph.join(' ')}
          </p>
        );
        currentParagraph = [];
      }
    };

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      if (trimmedLine.startsWith('## ')) {
        flushParagraph();
        elements.push(
          <h2
            key={elements.length}
            className="text-xl text-white mt-8 mb-4"
            style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
          >
            {trimmedLine.slice(3)}
          </h2>
        );
      } else if (trimmedLine.startsWith('### ')) {
        flushParagraph();
        elements.push(
          <h3
            key={elements.length}
            className="text-lg text-indigo-300 mt-6 mb-3 font-semibold"
          >
            {trimmedLine.slice(4)}
          </h3>
        );
      } else if (trimmedLine.startsWith('- ')) {
        flushParagraph();
        elements.push(
          <li key={elements.length} className="text-gray-300 ml-4 mb-2 flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-2 flex-shrink-0" />
            <span>{trimmedLine.slice(2)}</span>
          </li>
        );
      } else if (trimmedLine.match(/^\d+\.\s\*\*.*\*\*/)) {
        // Numbered list with bold
        flushParagraph();
        const match = trimmedLine.match(/^(\d+)\.\s\*\*(.*)\*\*\s*-?\s*(.*)/);
        if (match) {
          elements.push(
            <div key={elements.length} className="flex gap-3 mb-3">
              <span className="text-indigo-400 font-medium">{match[1]}.</span>
              <div>
                <span className="text-white font-semibold">{match[2]}</span>
                {match[3] && <span className="text-gray-400"> - {match[3]}</span>}
              </div>
            </div>
          );
        }
      } else if (trimmedLine === '') {
        flushParagraph();
      } else {
        // Handle inline bold with **text**
        const processedLine = trimmedLine.replace(
          /\*\*(.*?)\*\*/g,
          '<strong class="text-white font-semibold">$1</strong>'
        );
        currentParagraph.push(processedLine);
      }
    });

    flushParagraph();

    return elements.map((el, i) => {
      if (React.isValidElement(el) && el.type === 'p') {
        const content = (el.props as any).children;
        if (typeof content === 'string' && content.includes('<strong')) {
          return (
            <p
              key={i}
              className="text-gray-300 leading-relaxed mb-4"
              dangerouslySetInnerHTML={{ __html: content }}
            />
          );
        }
      }
      return el;
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header with Navigation */}
      <InternalPageHeader
        currentPage="research"
        breadcrumbs={[
          { label: 'Research', onClick: onBackToList },
          { label: article.title.length > 30 ? article.title.slice(0, 30) + '...' : article.title },
        ]}
        onNavigate={onNavigate}
      />

      {/* Article Content */}
      <article className="pt-28 pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-12">
            {/* Main Content */}
            <div className="flex-1">
              {/* Back Link */}
              <button
                onClick={onBackToList}
                className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-8"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Back to Articles</span>
              </button>

              {/* Title */}
              <h1
                className="text-3xl md:text-4xl text-white mb-4"
                style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
              >
                {article.title}
              </h1>

              {/* Short Description */}
              <p className="text-xl text-gray-400 mb-6 leading-relaxed">
                {article.shortDescription}
              </p>

              {/* Meta Info */}
              <div className="flex items-center gap-4 text-sm mb-8">
                <div className="flex items-center gap-1.5 text-gray-500">
                  <Calendar className="w-4 h-4" />
                  <span>{formatDate(article.publishedAt)}</span>
                </div>
                <div className="flex items-center gap-1.5 text-gray-500">
                  <User className="w-4 h-4" />
                  <span>{article.author}</span>
                </div>
              </div>

              {/* Separator */}
              <div className="border-t border-white/10 mb-8" />

              {/* Main Content */}
              <div className="prose prose-invert max-w-none">
                {renderContent(article.content)}
              </div>

              {/* Tags */}
              <div className="mt-12 pt-8 border-t border-white/10">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-gray-500 text-sm">Tags:</span>
                  {article.tags.map((tag) => (
                    <span
                      key={tag}
                      className="flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-sm"
                    >
                      <Tag className="w-3 h-3" />
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Sidebar - Article List Link */}
            <aside className="hidden lg:block w-64 flex-shrink-0">
              <div className="sticky top-28">
                <button
                  onClick={onBackToList}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-indigo-500/30 transition-all"
                >
                  <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                    <List className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div className="text-left">
                    <div className="text-white font-medium">Article List</div>
                    <div className="text-gray-500 text-xs">View all research</div>
                  </div>
                </button>

                {/* Reading Progress could go here */}
                <div className="mt-6 p-4 rounded-xl bg-white/5 border border-white/10">
                  <h4
                    className="text-sm text-white mb-2"
                    style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
                  >
                    Symbol-μ Research
                  </h4>
                  <p className="text-xs text-gray-500">
                    Exploring the technical foundations of cognitive AI.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </article>

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
          <button
            onClick={onBackToList}
            className="text-indigo-400 hover:text-indigo-300 text-sm transition-colors"
          >
            View all articles
          </button>
        </div>
      </footer>
    </div>
  );
}
