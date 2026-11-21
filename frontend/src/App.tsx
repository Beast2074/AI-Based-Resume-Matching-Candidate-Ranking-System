import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Upload from './pages/Upload';
import Ranking from './pages/Ranking';
import CandidateDetail from './pages/CandidateDetail';
import HowItWorks from './pages/HowItWorks';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-background text-textPrimary flex flex-col font-sans selection:bg-accentIndigo/30 selection:text-white">
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/upload/:jobId" element={<Upload />} />
              <Route path="/ranking/:jobId" element={<Ranking />} />
              <Route path="/candidates/:id" element={<CandidateDetail />} />
              <Route path="/how-it-works" element={<HowItWorks />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="border-t border-white/5 py-6 text-center text-xs text-textMuted font-mono">
            AI-Based Resume Matching &amp; Candidate Ranking System &bull; Production ATS Engine
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
