import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { CompatibilityGate } from "@/app/CompatibilityGate";
import { ScenarioCatalog } from "@/features/scenarios/ScenarioCatalog";
import { ScenarioLayout } from "@/features/scenarios/ScenarioLayout";
import { ScenarioOverview } from "@/features/scenarios/ScenarioOverview";
import { WorkflowScreen } from "@/features/workflow/WorkflowScreen";
import { RoleScreen } from "@/features/roles/RoleScreen";
import { RegistryScreen } from "@/features/registry/RegistryScreen";
import { EligibilityScreen } from "@/features/eligibility/EligibilityScreen";

export function App() {
  return (
    <AppShell>
      <CompatibilityGate>
        <Routes>
          <Route path="/" element={<Navigate to="/scenarios" replace />} />
          <Route path="/scenarios" element={<ScenarioCatalog />} />
          <Route path="/scenarios/:scenarioId" element={<ScenarioLayout />}>
            <Route index element={<ScenarioOverview />} />
            <Route path="workflow" element={<WorkflowScreen />} />
            <Route path="roles/:roleId" element={<RoleScreen />} />
            <Route path="registry" element={<RegistryScreen />} />
            <Route path="eligibility" element={<EligibilityScreen />} />
          </Route>
          <Route path="*" element={<Navigate to="/scenarios" replace />} />
        </Routes>
      </CompatibilityGate>
    </AppShell>
  );
}
