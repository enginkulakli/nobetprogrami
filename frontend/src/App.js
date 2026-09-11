import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/lib/theme";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Personnel from "@/pages/Personnel";
import Leaves from "@/pages/Leaves";
import Schedule from "@/pages/Schedule";
import Statistics from "@/pages/Statistics";
import Settings from "@/pages/Settings";

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/personeller" element={<Personnel />} />
            <Route path="/izinler" element={<Leaves />} />
            <Route path="/nobet" element={<Schedule />} />
            <Route path="/istatistikler" element={<Statistics />} />
            <Route path="/ayarlar" element={<Settings />} />
          </Routes>
        </Layout>
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
