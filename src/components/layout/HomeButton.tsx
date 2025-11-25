import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { House } from '@phosphor-icons/react';

export function HomeButton() {
  return (
    <Link to="/">
      <Button 
        variant="outline" 
        size="sm"
        className="h-10 px-4 gap-2 hover:border-accent/50 hover:bg-accent/10 transition-all"
      >
        <House size={18} weight="bold" />
        Home
      </Button>
    </Link>
  );
}
