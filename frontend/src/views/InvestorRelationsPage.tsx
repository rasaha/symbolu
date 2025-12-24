/**
 * Investor Relations & Contact Page
 *
 * Professional page for investors, partners, and general inquiries.
 * Features company information, investment highlights, and contact forms.
 */

import React, { useState } from 'react';
import {
  Layers,
  ArrowLeft,
  Mail,
  MapPin,
  Phone,
  Building2,
  TrendingUp,
  Users,
  Globe,
  CheckCircle,
  FileText,
  Download,
  Calendar,
  ChevronRight,
  Send,
  Briefcase,
  Shield,
  Target,
  Zap,
} from 'lucide-react';

interface InvestorRelationsPageProps {
  onBack: () => void;
}

type TabId = 'overview' | 'investors' | 'press' | 'contact';

export function InvestorRelationsPage({ onBack }: InvestorRelationsPageProps) {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    company: '',
    type: 'general',
    message: '',
  });
  const [formSubmitted, setFormSubmitted] = useState(false);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // In production, this would send to a backend
    console.log('Contact form submitted:', contactForm);
    setFormSubmitted(true);
    setTimeout(() => {
      setFormSubmitted(false);
      setContactForm({ name: '', email: '', company: '', type: 'general', message: '' });
    }, 3000);
  };

  const tabs = [
    { id: 'overview' as TabId, label: 'Overview', icon: Building2 },
    { id: 'investors' as TabId, label: 'For Investors', icon: TrendingUp },
    { id: 'press' as TabId, label: 'Press & Media', icon: FileText },
    { id: 'contact' as TabId, label: 'Contact Us', icon: Mail },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={onBack}
                className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Back</span>
              </button>
              <div className="w-px h-6 bg-white/10" />
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                  <Layers className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold">Symbol-U</span>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-white/10 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile Tab Navigation */}
      <div className="md:hidden fixed top-[73px] left-0 right-0 z-40 bg-slate-950/90 backdrop-blur-md border-b border-white/5 px-4 py-2 overflow-x-auto">
        <div className="flex gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-white/10 text-white'
                  : 'text-gray-400'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <main className="pt-32 md:pt-24 pb-20 px-6">
        <div className="max-w-6xl mx-auto">

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-16">
              {/* Hero */}
              <div className="text-center">
                <h1 className="text-4xl md:text-5xl font-bold mb-6">
                  <span className="bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-300">
                    Investor Relations
                  </span>
                </h1>
                <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                  Building the cognitive substrate for trustworthy AI
                </p>
              </div>

              {/* Company Highlights */}
              <div className="grid md:grid-cols-3 gap-6">
                <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-transparent border border-indigo-500/20">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center mb-4">
                    <Target className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Mission</h3>
                  <p className="text-gray-400 text-sm">
                    Deliver transparent, auditable AI interactions through structured cognitive architecture.
                  </p>
                </div>
                <div className="p-6 rounded-2xl bg-gradient-to-br from-purple-500/10 to-transparent border border-purple-500/20">
                  <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mb-4">
                    <Shield className="w-6 h-6 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Differentiation</h3>
                  <p className="text-gray-400 text-sm">
                    10-layer ontological substrate with full coherence tracking and governance controls.
                  </p>
                </div>
                <div className="p-6 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-transparent border border-emerald-500/20">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-4">
                    <Zap className="w-6 h-6 text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Market Opportunity</h3>
                  <p className="text-gray-400 text-sm">
                    Enterprise AI governance and explainability - a $20B+ market by 2028.
                  </p>
                </div>
              </div>

              {/* Key Metrics */}
              <div className="p-8 rounded-2xl bg-white/5 border border-white/10">
                <h2 className="text-2xl font-bold mb-8 text-center">Key Metrics</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                  <div className="text-center">
                    <div className="text-4xl font-bold text-indigo-400 mb-2">10</div>
                    <div className="text-gray-400 text-sm">Ontological Layers</div>
                  </div>
                  <div className="text-center">
                    <div className="text-4xl font-bold text-purple-400 mb-2">4</div>
                    <div className="text-gray-400 text-sm">Engine Tiers</div>
                  </div>
                  <div className="text-center">
                    <div className="text-4xl font-bold text-emerald-400 mb-2">3</div>
                    <div className="text-gray-400 text-sm">Product Lines</div>
                  </div>
                  <div className="text-center">
                    <div className="text-4xl font-bold text-amber-400 mb-2">100%</div>
                    <div className="text-gray-400 text-sm">Auditability</div>
                  </div>
                </div>
              </div>

              {/* Leadership */}
              <div>
                <h2 className="text-2xl font-bold mb-8 text-center">Leadership</h2>
                <div className="grid md:grid-cols-3 gap-6">
                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10 text-center">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 mx-auto mb-4 flex items-center justify-center">
                      <Users className="w-10 h-10 text-white" />
                    </div>
                    <h3 className="font-semibold mb-1">Founding Team</h3>
                    <p className="text-sm text-gray-400">
                      AI researchers and enterprise software veterans
                    </p>
                  </div>
                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10 text-center">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 mx-auto mb-4 flex items-center justify-center">
                      <Briefcase className="w-10 h-10 text-white" />
                    </div>
                    <h3 className="font-semibold mb-1">Advisory Board</h3>
                    <p className="text-sm text-gray-400">
                      Industry experts in AI governance and compliance
                    </p>
                  </div>
                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10 text-center">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 mx-auto mb-4 flex items-center justify-center">
                      <Globe className="w-10 h-10 text-white" />
                    </div>
                    <h3 className="font-semibold mb-1">Global Reach</h3>
                    <p className="text-sm text-gray-400">
                      Serving enterprises across NA, EU, and APAC
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Investors Tab */}
          {activeTab === 'investors' && (
            <div className="space-y-12">
              <div className="text-center">
                <h1 className="text-4xl font-bold mb-4">For Investors</h1>
                <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                  Join us in building the future of trustworthy AI
                </p>
              </div>

              {/* Investment Thesis */}
              <div className="p-8 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20">
                <h2 className="text-2xl font-bold mb-6">Investment Thesis</h2>
                <div className="grid md:grid-cols-2 gap-8">
                  <div>
                    <h3 className="font-semibold text-indigo-300 mb-3">The Problem</h3>
                    <ul className="space-y-2 text-gray-400 text-sm">
                      <li className="flex items-start gap-2">
                        <ChevronRight className="w-4 h-4 mt-0.5 text-indigo-400 flex-shrink-0" />
                        LLMs lack transparency and auditability
                      </li>
                      <li className="flex items-start gap-2">
                        <ChevronRight className="w-4 h-4 mt-0.5 text-indigo-400 flex-shrink-0" />
                        Enterprise AI adoption blocked by governance concerns
                      </li>
                      <li className="flex items-start gap-2">
                        <ChevronRight className="w-4 h-4 mt-0.5 text-indigo-400 flex-shrink-0" />
                        No structured framework for AI response quality
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-semibold text-purple-300 mb-3">Our Solution</h3>
                    <ul className="space-y-2 text-gray-400 text-sm">
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 mt-0.5 text-emerald-400 flex-shrink-0" />
                        10-layer cognitive substrate with full traceability
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 mt-0.5 text-emerald-400 flex-shrink-0" />
                        Built-in governance gates and coherence metrics
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 mt-0.5 text-emerald-400 flex-shrink-0" />
                        Tiered architecture for diverse deployment needs
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Market Opportunity */}
              <div className="grid md:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                  <TrendingUp className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="font-semibold mb-2">TAM / SAM / SOM</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Total Addressable Market</span>
                      <span className="text-white font-medium">$50B+</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Serviceable Market</span>
                      <span className="text-white font-medium">$20B</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Initial Target</span>
                      <span className="text-white font-medium">$500M</span>
                    </div>
                  </div>
                </div>
                <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                  <Target className="w-8 h-8 text-indigo-400 mb-4" />
                  <h3 className="font-semibold mb-2">Go-to-Market</h3>
                  <ul className="space-y-2 text-sm text-gray-400">
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      Enterprise pilot programs
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      Strategic platform partnerships
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      Developer community building
                    </li>
                  </ul>
                </div>
              </div>

              {/* Documents */}
              <div>
                <h2 className="text-2xl font-bold mb-6">Investor Materials</h2>
                <div className="grid md:grid-cols-3 gap-4">
                  <button className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-indigo-500/30 transition-colors text-left">
                    <Download className="w-5 h-5 text-indigo-400" />
                    <div>
                      <div className="font-medium text-sm">Pitch Deck</div>
                      <div className="text-xs text-gray-500">PDF, 2.4 MB</div>
                    </div>
                  </button>
                  <button className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-indigo-500/30 transition-colors text-left">
                    <Download className="w-5 h-5 text-purple-400" />
                    <div>
                      <div className="font-medium text-sm">Technical Whitepaper</div>
                      <div className="text-xs text-gray-500">PDF, 1.8 MB</div>
                    </div>
                  </button>
                  <button className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-indigo-500/30 transition-colors text-left">
                    <Download className="w-5 h-5 text-emerald-400" />
                    <div>
                      <div className="font-medium text-sm">Financial Model</div>
                      <div className="text-xs text-gray-500">XLSX, 450 KB</div>
                    </div>
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-4">
                  * Contact us to request access to investor materials
                </p>
              </div>
            </div>
          )}

          {/* Press Tab */}
          {activeTab === 'press' && (
            <div className="space-y-12">
              <div className="text-center">
                <h1 className="text-4xl font-bold mb-4">Press & Media</h1>
                <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                  News, announcements, and media resources
                </p>
              </div>

              {/* Press Releases */}
              <div>
                <h2 className="text-2xl font-bold mb-6">Recent News</h2>
                <div className="space-y-4">
                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                    <div className="flex items-center gap-2 text-sm text-indigo-400 mb-2">
                      <Calendar className="w-4 h-4" />
                      <span>December 2025</span>
                    </div>
                    <h3 className="text-lg font-semibold mb-2">
                      Symbol-U Launches Three-Tier Enterprise AI Platform
                    </h3>
                    <p className="text-gray-400 text-sm mb-4">
                      New cognitive framework brings unprecedented transparency and governance to enterprise AI deployments.
                    </p>
                    <button className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                      Read more <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                    <div className="flex items-center gap-2 text-sm text-purple-400 mb-2">
                      <Calendar className="w-4 h-4" />
                      <span>November 2025</span>
                    </div>
                    <h3 className="text-lg font-semibold mb-2">
                      Symbol-U Announces Seed Funding Round
                    </h3>
                    <p className="text-gray-400 text-sm mb-4">
                      Investment will accelerate development of 10-layer ontological AI substrate.
                    </p>
                    <button className="text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1">
                      Read more <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Media Kit */}
              <div>
                <h2 className="text-2xl font-bold mb-6">Media Kit</h2>
                <div className="grid md:grid-cols-2 gap-4">
                  <button className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                      <Layers className="w-6 h-6 text-indigo-400" />
                    </div>
                    <div>
                      <div className="font-medium">Logo Pack</div>
                      <div className="text-xs text-gray-500">SVG, PNG, PDF formats</div>
                    </div>
                    <Download className="w-5 h-5 text-gray-400 ml-auto" />
                  </button>
                  <button className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left">
                    <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                      <FileText className="w-6 h-6 text-purple-400" />
                    </div>
                    <div>
                      <div className="font-medium">Brand Guidelines</div>
                      <div className="text-xs text-gray-500">PDF, 3.2 MB</div>
                    </div>
                    <Download className="w-5 h-5 text-gray-400 ml-auto" />
                  </button>
                </div>
              </div>

              {/* Media Contact */}
              <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20">
                <h3 className="font-semibold mb-4">Media Inquiries</h3>
                <p className="text-gray-400 text-sm mb-4">
                  For press inquiries, interview requests, or media resources, please contact our communications team.
                </p>
                <a
                  href="mailto:press@symbolu.ai"
                  className="inline-flex items-center gap-2 text-indigo-400 hover:text-indigo-300"
                >
                  <Mail className="w-4 h-4" />
                  press@symbolu.ai
                </a>
              </div>
            </div>
          )}

          {/* Contact Tab */}
          {activeTab === 'contact' && (
            <div className="space-y-12">
              <div className="text-center">
                <h1 className="text-4xl font-bold mb-4">Contact Us</h1>
                <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                  We'd love to hear from you
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-12">
                {/* Contact Form */}
                <div>
                  <h2 className="text-xl font-bold mb-6">Send a Message</h2>
                  {formSubmitted ? (
                    <div className="p-8 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-center">
                      <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
                      <h3 className="text-lg font-semibold mb-2">Message Sent!</h3>
                      <p className="text-gray-400 text-sm">
                        Thank you for reaching out. We'll get back to you soon.
                      </p>
                    </div>
                  ) : (
                    <form onSubmit={handleFormSubmit} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-2">Name *</label>
                        <input
                          type="text"
                          required
                          value={contactForm.name}
                          onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                          className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                          placeholder="Your name"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Email *</label>
                        <input
                          type="email"
                          required
                          value={contactForm.email}
                          onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                          className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                          placeholder="you@company.com"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Company</label>
                        <input
                          type="text"
                          value={contactForm.company}
                          onChange={(e) => setContactForm({ ...contactForm, company: e.target.value })}
                          className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                          placeholder="Your company (optional)"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Inquiry Type</label>
                        <select
                          value={contactForm.type}
                          onChange={(e) => setContactForm({ ...contactForm, type: e.target.value })}
                          className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                        >
                          <option value="general">General Inquiry</option>
                          <option value="investor">Investment Opportunity</option>
                          <option value="partnership">Partnership</option>
                          <option value="enterprise">Enterprise Sales</option>
                          <option value="press">Press / Media</option>
                          <option value="careers">Careers</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Message *</label>
                        <textarea
                          required
                          rows={4}
                          value={contactForm.message}
                          onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                          className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 resize-none"
                          placeholder="How can we help?"
                        />
                      </div>
                      <button
                        type="submit"
                        className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold hover:from-indigo-500 hover:to-purple-500 transition-all"
                      >
                        <Send className="w-4 h-4" />
                        Send Message
                      </button>
                    </form>
                  )}
                </div>

                {/* Contact Info */}
                <div className="space-y-6">
                  <h2 className="text-xl font-bold mb-6">Get in Touch</h2>

                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                        <Mail className="w-5 h-5 text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="font-medium mb-1">Email</h3>
                        <a href="mailto:hello@symbolu.ai" className="text-gray-400 hover:text-indigo-400 transition-colors">
                          hello@symbolu.ai
                        </a>
                      </div>
                    </div>
                  </div>

                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                        <MapPin className="w-5 h-5 text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-medium mb-1">Location</h3>
                        <p className="text-gray-400 text-sm">
                          San Francisco, CA<br />
                          United States
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                        <Phone className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div>
                        <h3 className="font-medium mb-1">Phone</h3>
                        <p className="text-gray-400 text-sm">
                          Available upon request
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Social Links */}
                  <div className="pt-6 border-t border-white/10">
                    <h3 className="font-medium mb-4">Follow Us</h3>
                    <div className="flex gap-3">
                      <a href="#" className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors">
                        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                        </svg>
                      </a>
                      <a href="#" className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors">
                        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                        </svg>
                      </a>
                      <a href="#" className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors">
                        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                          <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd"/>
                        </svg>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-gray-500 text-sm">
            &copy; 2025 Symbol-U. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
