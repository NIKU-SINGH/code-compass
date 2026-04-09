"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  ListTodo,
  Zap,
  Settings,
  HelpCircle,
  Library,
  Compass,
  PanelLeft,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { label: "Home", icon: Home, href: "/" },
  { label: "Projects", icon: ListTodo, href: "/projects" },
  { label: "Automations", icon: Zap, href: "#" },
];

const RECENT_PROJECTS = [
  { id: "demo", label: "code-compass" },
  { id: "sample-1", label: "my-api-service" },
];

const FOOTER_ITEMS = [
  { label: "Settings", icon: Settings, href: "#" },
  { label: "Help", icon: HelpCircle, href: "#" },
  { label: "Resources", icon: Library, href: "#" },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { state, toggleSidebar } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center">
          <SidebarMenu className="flex-1">
            <SidebarMenuItem>
              {collapsed ? (
                <SidebarMenuButton
                  size="lg"
                  onClick={toggleSidebar}
                  className="group/logo"
                  tooltip="Expand sidebar"
                >
                  <div className="size-7 rounded bg-primary flex items-center justify-center shrink-0 relative">
                    <Compass className="size-4 text-primary-foreground transition-opacity group-hover/logo:opacity-0" />
                    <PanelLeft className="size-4 text-primary-foreground absolute inset-0 m-auto opacity-0 transition-opacity group-hover/logo:opacity-100" />
                  </div>
                </SidebarMenuButton>
              ) : (
                <SidebarMenuButton size="lg" asChild>
                  <Link href="/">
                    <div className="size-7 rounded bg-primary flex items-center justify-center shrink-0">
                      <Compass className="size-4 text-primary-foreground" />
                    </div>
                    <span className="font-semibold text-foreground">Code Compass</span>
                  </Link>
                </SidebarMenuButton>
              )}
            </SidebarMenuItem>
          </SidebarMenu>
          {!collapsed && <SidebarTrigger />}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Recent Projects</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {RECENT_PROJECTS.map((project) => (
                <SidebarMenuItem key={project.id}>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname === `/project/${project.id}`}
                  >
                    <Link href={`/project/${project.id}`}>
                      <span className="size-1.5 rounded-full shrink-0 bg-muted-foreground/40" />
                      <span className="truncate">{project.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
        <SidebarMenu>
          {FOOTER_ITEMS.map((item) => (
            <SidebarMenuItem key={item.label}>
              <SidebarMenuButton asChild>
                <Link href={item.href}>
                  <item.icon />
                  <span>{item.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
