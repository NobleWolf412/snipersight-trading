import { Toaster } from '@/components/ui/sonner';
import { Landing } from '@/pages/Landing';

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground tactical-grid">
      <main>
        <Landing />
      </main>
      <Toaster />
    </div>
  );
}

export default App;
