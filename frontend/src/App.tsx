/**
 * Symbol-U Frontend App
 *
 * Main application with home page and three-tier UX routing.
 *
 * Pages:
 * - Home: Introduction to Symbol-U with vision and demo link
 * - Products: Product overview page with tier comparisons
 * - Product Detail: Individual tier product pages with detailed features
 * - Tier Selector: Choose between Consumer, Power User, or Admin
 * - Consumer: Simple chat with badges & hints
 * - Power User: Chat + insights panel with metrics
 * - Admin: Full dashboard with analytics & simulations
 */

import React, { useState, useEffect } from 'react';
import type { PresentationTier } from '@/api/types';
import { HomePage } from '@/views/HomePage';
import { ProductsPage } from '@/views/ProductsPage';
import { ConsumerProductPage, PowerUserProductPage, AdminProductPage } from '@/views/products';
import { ConsumerTierPage } from '@/views/ConsumerTierPage';
import { PowerUserTierPage } from '@/views/PowerUserTierPage';
import { AdminTierPage } from '@/views/AdminTierPage';
import { useChatStore } from '@/stores/chatStore';
import { Layers, User, Shield, Home, ArrowLeft, Package } from 'lucide-react';

type AppPage = 'home' | 'products' | 'product_detail' | 'selector' | 'tier';

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
          {/* Consumer Tier */}
          <button
            onClick={() => onSelectTier('consumer')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-blue-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-blue-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <User className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Consumer</h3>
            <p className="text-gray-400 text-sm mb-4">
              Simple, clean chat experience with helpful insights and badges.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Chat interface
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Response badges
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

          {/* Power User Tier */}
          <button
            onClick={() => onSelectTier('power_user')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-purple-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-purple-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Layers className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Power User</h3>
            <p className="text-gray-400 text-sm mb-4">
              Enhanced insights with layer analysis and coherence metrics.
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

          {/* Admin Tier */}
          <button
            onClick={() => onSelectTier('admin')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-orange-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-orange-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Admin</h3>
            <p className="text-gray-400 text-sm mb-4">
              Full analytics dashboard with simulations and diagnostics.
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
  const setTier = useChatStore((state) => state.setTier);

  // Check URL for page/tier parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pageParam = params.get('page');
    const tierParam = params.get('tier');
    const productParam = params.get('product');

    if (tierParam && ['consumer', 'power_user', 'admin'].includes(tierParam)) {
      setSelectedTier(tierParam as PresentationTier);
      setTier(tierParam as PresentationTier);
      setCurrentPage('tier');
    } else if (productParam && ['consumer', 'power_user', 'admin'].includes(productParam)) {
      setSelectedProductTier(productParam as PresentationTier);
      setCurrentPage('product_detail');
    } else if (pageParam === 'products') {
      setCurrentPage('products');
    } else if (pageParam === 'demo') {
      setCurrentPage('selector');
    }
  }, [setTier]);

  // Update URL helper
  const updateURL = (page: AppPage, tier?: PresentationTier, product?: PresentationTier) => {
    const url = new URL(window.location.href);
    url.search = '';

    if (page === 'tier' && tier) {
      url.searchParams.set('tier', tier);
    } else if (page === 'product_detail' && product) {
      url.searchParams.set('product', product);
    } else if (page === 'products') {
      url.searchParams.set('page', 'products');
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

  // Handle tier selection
  const handleSelectTier = (tier: PresentationTier) => {
    setSelectedTier(tier);
    setTier(tier);
    setCurrentPage('tier');
    updateURL('tier', tier);
  };

  // Handle product tier selection (Learn More)
  const handleSelectProductTier = (tier: PresentationTier) => {
    setSelectedProductTier(tier);
    setCurrentPage('product_detail');
    updateURL('product_detail', undefined, tier);
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

  // Handle back to home
  const handleBackToHome = () => {
    setSelectedTier(null);
    setSelectedProductTier(null);
    setCurrentPage('home');
    updateURL('home');
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

  if (currentPage === 'selector' || (!selectedTier && currentPage !== 'product_detail')) {
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
