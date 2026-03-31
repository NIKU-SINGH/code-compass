import {
  Home,
  ListTodo,
  Zap,
  Settings,
  HelpCircle,
  Library,
  Compass,
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
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { label: "Home", icon: Home, href: "/" },
  { label: "Tasks", icon: ListTodo, href: "/tasks", active: true },
  { label: "Automations", icon: Zap, href: "/automations" },
];

const RECENT_TASKS = [
  { id: "1", label: "Repository Purpose Overview", active: true },
  { id: "2", label: "Explain the purpose and overview...", active: false },
  { id: "3", label: "Set up CI pipeline", active: false },
];

const FOOTER_ITEMS = [
  { label: "Settings", icon: Settings, href: "#" },
  { label: "Help", icon: HelpCircle, href: "#" },
  { label: "Resources", icon: Library, href: "#" },
];

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a href="/">
                <div className="size-7 rounded bg-primary flex items-center justify-center shrink-0">
                  <Compass className="size-4 text-primary-foreground" />
                </div>
                <span className="font-semibold text-foreground">Code Compass</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {/* Main navigation */}
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton asChild isActive={item.active}>
                    <a href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        {/* Recent Tasks */}
        <SidebarGroup>
          <SidebarGroupLabel>Recent Tasks</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {RECENT_TASKS.map((task) => (
                <SidebarMenuItem key={task.id}>
                  <SidebarMenuButton asChild>
                    <a href={`/tasks/${task.id}`}>
                      <span
                        className={`size-1.5 rounded-full shrink-0 ${
                          task.active ? "bg-green-500" : "bg-muted-foreground/40"
                        }`}
                      />
                      <span className="truncate">{task.label}</span>
                    </a>
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
                <a href={item.href}>
                  <item.icon />
                  <span>{item.label}</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

export { SidebarTrigger };
