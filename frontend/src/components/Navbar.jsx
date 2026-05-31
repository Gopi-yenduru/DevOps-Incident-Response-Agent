import { Link, useLocation } from 'react-router-dom';
import { Activity, BarChart2, Server } from 'lucide-react';
import clsx from 'clsx';

export default function Navbar() {
  const location = useLocation();

  const links = [
    { name: 'Dashboard', path: '/', icon: Activity },
    { name: 'Analytics', path: '/analytics', icon: BarChart2 },
  ];

  return (
    <nav className="bg-devops-card border-b border-devops-border sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <Server className="h-6 w-6 text-blue-500" />
            <Link to="/" className="text-xl font-bold text-white tracking-tight">
              DevOps<span className="text-blue-500">Agent</span>
            </Link>
          </div>
          
          <div className="flex space-x-1">
            {links.map((link) => {
              const Icon = link.icon;
              const isActive = location.pathname === link.path || 
                               (link.path !== '/' && location.pathname.startsWith(link.path));
              return (
                <Link
                  key={link.name}
                  to={link.path}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                    isActive 
                      ? "bg-slate-800 text-white" 
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {link.name}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
