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
import { RankingScreen } from "@/features/ranking/RankingScreen";
import { CompositionScreen } from "@/features/composition/CompositionScreen";
import { PermissionScreen } from "@/features/permissions/PermissionScreen";
import { FallbackScreen } from "@/features/fallbacks/FallbackScreen";
import { ReplayScreen } from "@/features/replay/ReplayScreen";
import { CompareScreen } from "@/features/compare/CompareScreen";
import { WhatIfScreen } from "@/features/whatif/WhatIfScreen";
import { BringYourWorkflowScreen } from "@/features/bring/BringYourWorkflowScreen";
// Governed Agent Studio (GAS-4/5) — additive, mounted alongside the v1 explorer.
import {
  AuthorityScreen,
  ConstitutionScreen,
  DataUseScreen,
  VendorScreen,
  ObserveScreen,
  PolicyScreen,
  PublishScreen,
  RegistrationScreen,
  ReviewQueueScreen,
  RunDetailScreen,
  SimulateScreen,
  StatusScreen,
  StudioLayout,
} from "@/features/studio";
import {
  FROZEN_APPROVAL_RECORD,
  FROZEN_POLICY_PACK,
} from "@/features/studio/fixtures/frozenPack";

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
            <Route path="ranking" element={<RankingScreen />} />
            <Route path="composition" element={<CompositionScreen />} />
            <Route path="permissions" element={<PermissionScreen />} />
            <Route path="fallbacks" element={<FallbackScreen />} />
            <Route path="replay" element={<ReplayScreen />} />
            <Route path="compare" element={<CompareScreen />} />
            <Route path="what-if" element={<WhatIfScreen />} />
          </Route>
          <Route path="/bring-your-workflow" element={<BringYourWorkflowScreen />} />
          <Route path="/studio" element={<StudioLayout />}>
            <Route index element={<Navigate to="constitution" replace />} />
            {/* Front-door seam 5 (FD-9): typed registration intake; register is the only write. */}
            <Route path="registration" element={<RegistrationScreen />} />
            {/* Front-door seam 8 (FD-12): typed data-use declarations; declare is the only write. */}
            <Route path="data-use" element={<DataUseScreen />} />
            {/* Front-door seam 9 (FD-13): typed vendor declarations; declare is the only write. */}
            <Route path="vendor" element={<VendorScreen />} />
            <Route path="constitution" element={<ConstitutionScreen />} />
            <Route
              path="policy"
              element={
                <PolicyScreen pack={FROZEN_POLICY_PACK} approval={FROZEN_APPROVAL_RECORD} />
              }
            />
            <Route path="authority" element={<AuthorityScreen />} />
            <Route path="simulate" element={<SimulateScreen />} />
            <Route path="publish" element={<PublishScreen />} />
            <Route path="observe" element={<ObserveScreen />} />
            {/* GAS-7 HR-D: Review Queue and Run Detail, display and relay only. */}
            <Route path="review" element={<ReviewQueueScreen />} />
            <Route path="review/:instanceId" element={<RunDetailScreen />} />
            {/* MA-2 as amended (MS-5): the Status panel, one read of the startup attestation. */}
            <Route path="status" element={<StatusScreen />} />
          </Route>
          <Route path="*" element={<Navigate to="/scenarios" replace />} />
        </Routes>
      </CompatibilityGate>
    </AppShell>
  );
}
