import { MainLayout } from "@/components/layout/MainLayout";
import { HomePage } from "@/pages/HomePage";

export function App() {
  return (
    <div className="dark">
      <MainLayout>
        <HomePage />
      </MainLayout>
    </div>
  );
}
