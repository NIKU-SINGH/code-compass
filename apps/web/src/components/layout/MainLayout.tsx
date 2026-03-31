import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar, SidebarTrigger } from "./Sidebar";

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <SidebarTrigger />
        </div>
        {children}
      </main>
    </SidebarProvider>
  );
}
