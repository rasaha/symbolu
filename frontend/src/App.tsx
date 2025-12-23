/**
 * Symbol-U Frontend App
 *
 * Main application with home page and three-tier UX routing.
 *
 * Pages:
 * - Home: Introduction to Symbol-U with vision and demo link
 * - Products: Product overview page with tier comparisons
 * - Product Detail: Individual tier product pages with detailed features
 * - Research: Article listing page
 * - Article: Individual article view
 * - Tier Selector: Choose between Explorer, Analyst, or Developer
 * - Explorer: Simple search with badges & hints
 * - Analyst: Enterprise chat + insights panel with metrics
 * - Developer: Customer chat with full dashboard and analytics
 */

import React, { useState, useEffect } from 'react';
import type { PresentationTier } from '@/api/types';
import { HomePage } from '@/views/HomePage';
import { ProductsPage } from '@/views/ProductsPage';
import { ResearchPage } from '@/views/ResearchPage';
import { ArticlePage } from '@/views/ArticlePage';
import { ConsumerProductPage, PowerUserProductPage, AdminProductPage } from '@/views/products';
import { ConsumerTierPage } from '@/views/ConsumerTierPage';
import { PowerUserTierPage } from '@/views/PowerUserTierPage';
import { AdminTierPage } from '@/views/AdminTierPage';
import { useChatStore } from '@/stores/chatStore';
import { Layers, Search, Code, Home, ArrowLeft, Package } from 'lucide-react';
import type { PageId } from '@/components/common/PageNavigation';

type AppPage = 'home' | 'products' | 'product_detail' | 'research' | 'article' | 'selector' | 'tier';

// Landing page for tier selection
function TierSelector({
  onSelectTier,
  onBackToHome,
}: {
  onSelectTier: (tier: PresentationTier) => void;
  onBackToHome: () => void;
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-slate-900 flex items-center justify-center p-6">
      <div className="max-w-4xl w-full">
        {/* Back to Home */}
        <button
          onClick={onBackToHome}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Home</span>
        </button>

        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-6 shadow-2xl">
            <Layers className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-4">Choose Your Experience</h1>
          <p className="text-gray-400 text-lg max-w-md mx-auto">
            Select the tier that matches your needs. Each tier provides progressively more features and insights.
          </p>
        </div>

        {/* Tier Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {/* Explorer Tier - Knowledge Base Lookup */}
          <button
            onClick={() => onSelectTier('consumer')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-blue-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-blue-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Search className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Explorer</h3>
            <p className="text-blue-400 text-xs font-medium mb-2">RAG Lookup</p>
            <p className="text-gray-400 text-sm mb-4">
              Simple RAG-powered search with quality indicators and hints.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Search interface
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Quality badges
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Hint cards
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>

          {/* Analyst Tier - Enterprise Chat */}
          <button
            onClick={() => onSelectTier('power_user')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-purple-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-purple-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Layers className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Analyst</h3>
            <p className="text-purple-400 text-xs font-medium mb-2">Enterprise Chat</p>
            <p className="text-gray-400 text-sm mb-4">
              Internal employee chat with semantic insights and metrics.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Layer tabs (Symbolic/Practical/Mirror)
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Entropy metrics
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Ontological profile
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>

          {/* Developer Tier - Customer Chat */}
          <button
            onClick={() => onSelectTier('admin')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-orange-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-orange-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Code className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Developer</h3>
            <p className="text-orange-400 text-xs font-medium mb-2">Customer Chat</p>
            <p className="text-gray-400 text-sm mb-4">
              External customer chat with full analytics and diagnostics.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Coherence trend charts
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Risk bands & timeline
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                What-if simulator
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-orange-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-gray-500 text-sm">
          <p>Symbol-U Frontend v0.1 | Three-Tier UX</p>
        </div>
      </div>
    </div>
  );
}

// Main App Component
export function App() {
  const [currentPage, setCurrentPage] = useState<AppPage>('home');
  const [selectedTier, setSelectedTier] = useState<PresentationTier | null>(null);
  const [selectedProductTier, setSelectedProductTier] = useState<PresentationTier | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<string | null>(null);
  const setTier = useChatStore((state) => state.setTier);

  // Check URL for page/tier parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pageParam = params.get('page');
    const tierParam = params.get('tier');
    const productParam = params.get('product');
    const articleParam = params.get('article');

    if (tierParam && ['consumer', 'power_user', 'admin'].includes(tierParam)) {
      setSelectedTier(tierParam as PresentationTier);
      setTier(tierParam as PresentationTier);
      setCurrentPage('tier');
    } else if (productParam && ['consumer', 'power_user', 'admin'].includes(productParam)) {
      setSelectedProductTier(productParam as PresentationTier);
      setCurrentPage('product_detail');
    } else if (articleParam) {
      setSelectedArticle(articleParam);
      setCurrentPage('article');
    } else if (pageParam === 'products') {
      setCurrentPage('products');
    } else if (pageParam === 'research') {
      setCurrentPage('research');
    } else if (pageParam === 'demo') {
      setCurrentPage('selector');
    }
  }, [setTier]);

  // Update URL helper
  const updateURL = (page: AppPage, options?: { tier?: PresentationTier; product?: PresentationTier; article?: string }) => {
    const url = new URL(window.location.href);
    url.search = '';

    if (page === 'tier' && options?.tier) {
      url.searchParams.set('tier', options.tier);
    } else if (page === 'product_detail' && options?.product) {
      url.searchParams.set('product', options.product);
    } else if (page === 'article' && options?.article) {
      url.searchParams.set('article', options.article);
    } else if (page === 'products') {
      url.searchParams.set('page', 'products');
    } else if (page === 'research') {
      url.searchParams.set('page', 'research');
    } else if (page === 'selector') {
      url.searchParams.set('page', 'demo');
    }

    window.history.pushState({}, '', url.toString());
  };

  // Handle entering demo (tier selector)
  const handleEnterDemo = () => {
    setCurrentPage('selector');
    updateURL('selector');
  };

  // Handle navigating to products page
  const handleGoToProducts = () => {
    setCurrentPage('products');
    updateURL('products');
  };

  // Handle navigating to research page
  const handleGoToResearch = () => {
    setCurrentPage('research');
    updateURL('research');
  };

  // Handle tier selection
  const handleSelectTier = (tier: PresentationTier) => {
    setSelectedTier(tier);
    setTier(tier);
    setCurrentPage('tier');
    updateURL('tier', { tier });
  };

  // Handle product tier selection (Learn More)
  const handleSelectProductTier = (tier: PresentationTier) => {
    setSelectedProductTier(tier);
    setCurrentPage('product_detail');
    updateURL('product_detail', { product: tier });
  };

  // Handle article selection
  const handleSelectArticle = (articleId: string) => {
    setSelectedArticle(articleId);
    setCurrentPage('article');
    updateURL('article', { article: articleId });
  };

  // Handle back to tier selector
  const handleBackToSelector = () => {
    setSelectedTier(null);
    setCurrentPage('selector');
    updateURL('selector');
  };

  // Handle back to products
  const handleBackToProducts = () => {
    setSelectedProductTier(null);
    setCurrentPage('products');
    updateURL('products');
  };

  // Handle back to research
  const handleBackToResearch = () => {
    setSelectedArticle(null);
    setCurrentPage('research');
    updateURL('research');
  };

  // Handle back to home
  const handleBackToHome = () => {
    setSelectedTier(null);
    setSelectedProductTier(null);
    setSelectedArticle(null);
    setCurrentPage('home');
    updateURL('home');
  };

  // Handle PageNavigation navigation
  const handlePageNavigate = (pageId: PageId) => {
    switch (pageId) {
      case 'home':
        handleBackToHome();
        break;
      case 'products':
        handleGoToProducts();
        break;
      case 'research':
        handleGoToResearch();
        break;
      case 'demo':
        handleEnterDemo();
        break;
    }
  };

  // Render based on current page
  if (currentPage === 'home') {
    return <HomePage onEnterDemo={handleEnterDemo} onGoToProducts={handleGoToProducts} />;
  }

  if (currentPage === 'products') {
    return (
      <ProductsPage
        onSelectProductTier={handleSelectProductTier}
        onTryDemo={handleSelectTier}
        onBackToHome={handleBackToHome}
      />
    );
  }

  if (currentPage === 'product_detail' && selectedProductTier) {
    const productComponents: Record<PresentationTier, React.ReactNode> = {
      consumer: (
        <ConsumerProductPage
          onTryDemo={() => handleSelectTier('consumer')}
          onBack={handleBackToProducts}
        />
      ),
      power_user: (
        <PowerUserProductPage
          onTryDemo={() => handleSelectTier('power_user')}
          onBack={handleBackToProducts}
        />
      ),
      admin: (
        <AdminProductPage
          onTryDemo={() => handleSelectTier('admin')}
          onBack={handleBackToProducts}
        />
      ),
    };

    return productComponents[selectedProductTier];
  }

  if (currentPage === 'research') {
    return (
      <ResearchPage
        onNavigate={handlePageNavigate}
        onSelectArticle={handleSelectArticle}
      />
    );
  }

  if (currentPage === 'article' && selectedArticle) {
    return (
      <ArticlePage
        articleId={selectedArticle}
        onNavigate={handlePageNavigate}
        onBackToList={handleBackToResearch}
      />
    );
  }

  if (currentPage === 'selector' || (!selectedTier && currentPage !== 'product_detail' && currentPage !== 'research' && currentPage !== 'article')) {
    return (
      <TierSelector
        onSelectTier={handleSelectTier}
        onBackToHome={handleBackToHome}
      />
    );
  }

  // Render appropriate tier page with navigation
  const tierComponents: Record<PresentationTier, React.ReactNode> = {
    consumer: <ConsumerTierPage />,
    power_user: <PowerUserTierPage />,
    admin: <AdminTierPage />,
  };

  return (
    <div className="relative">
      {/* Navigation Buttons */}
      <div className="fixed top-4 left-4 z-50 flex items-center gap-2">
        <button
          onClick={handleBackToHome}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/20 backdrop-blur text-white/80 text-xs font-medium hover:bg-black/30 transition-colors"
          title="Back to Home"
        >
          <Home className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleBackToSelector}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/20 backdrop-blur text-white/80 text-xs font-medium hover:bg-black/30 transition-colors"
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Change Tier</span>
        </button>
      </div>

      {/* Tier Page */}
      {tierComponents[selectedTier!]}
    </div>
  );
}

export default App;
