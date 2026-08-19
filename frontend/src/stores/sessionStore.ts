import { create } from 'zustand';
import type {
  QueryResponse,
  CareGapResult,
  CoverageMap,
  TrendResult,
} from '../api/types';

export interface ConsoleSession {
  query: string;
  status: 'idle' | 'loading' | 'verified' | 'refused' | 'error';
  result: QueryResponse | null;
  searchPrivate: boolean;
}

export interface CareGapSession {
  status: 'idle' | 'loading' | 'success' | 'error';
  result: CareGapResult | null;
}

export interface CoverageSession {
  query: string;
  status: 'idle' | 'loading' | 'success' | 'error';
  result: CoverageMap | null;
}

export interface MedTrendSession {
  status: 'idle' | 'loading' | 'success' | 'error';
  result: TrendResult | null;
}

export interface ReportsSession {
  selectedReportId: string | null;
}

export interface AppSessionState {
  console: ConsoleSession;
  caregap: CareGapSession;
  coverage: CoverageSession;
  medtrend: MedTrendSession;
  reports: ReportsSession;

  setConsoleState: (partial: Partial<ConsoleSession>) => void;
  setCareGapState: (partial: Partial<CareGapSession>) => void;
  setCoverageState: (partial: Partial<CoverageSession>) => void;
  setMedTrendState: (partial: Partial<MedTrendSession>) => void;
  setReportsState: (partial: Partial<ReportsSession>) => void;
  clearSession: () => void;
}

const SESSION_STORAGE_KEY = 'medgraphrag.session';

const initialConsole: ConsoleSession = {
  query: '',
  status: 'idle',
  result: null,
  searchPrivate: false,
};

const initialCareGap: CareGapSession = {
  status: 'idle',
  result: null,
};

const initialCoverage: CoverageSession = {
  query: 'warfarin INR monitoring guidelines atrial fibrillation',
  status: 'idle',
  result: null,
};

const initialMedTrend: MedTrendSession = {
  status: 'idle',
  result: null,
};

const initialReports: ReportsSession = {
  selectedReportId: null,
};

function loadHydratedSession() {
  if (typeof window === 'undefined') {
    return {
      console: initialConsole,
      caregap: initialCareGap,
      coverage: initialCoverage,
      medtrend: initialMedTrend,
      reports: initialReports,
    };
  }

  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        console: { ...initialConsole, ...parsed.console },
        caregap: { ...initialCareGap, ...parsed.caregap },
        coverage: { ...initialCoverage, ...parsed.coverage },
        medtrend: { ...initialMedTrend, ...parsed.medtrend },
        reports: { ...initialReports, ...parsed.reports },
      };
    }
  } catch (e) {
    console.warn('Failed to parse hydrated session from sessionStorage', e);
  }

  return {
    console: initialConsole,
    caregap: initialCareGap,
    coverage: initialCoverage,
    medtrend: initialMedTrend,
    reports: initialReports,
  };
}

function saveToSessionStorage(state: {
  console: ConsoleSession;
  caregap: CareGapSession;
  coverage: CoverageSession;
  medtrend: MedTrendSession;
  reports: ReportsSession;
}) {
  if (typeof window === 'undefined') return;
  try {
    const payload = {
      console: state.console,
      caregap: state.caregap,
      coverage: state.coverage,
      medtrend: state.medtrend,
      reports: state.reports,
    };
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn('Failed to write-through session to sessionStorage', e);
  }
}

const hydrated = loadHydratedSession();

export const useSessionStore = create<AppSessionState>((set) => ({
  console: hydrated.console,
  caregap: hydrated.caregap,
  coverage: hydrated.coverage,
  medtrend: hydrated.medtrend,
  reports: hydrated.reports,

  setConsoleState: (partial) =>
    set((state) => {
      const updated = { ...state.console, ...partial };
      const nextState = { ...state, console: updated };
      saveToSessionStorage(nextState);
      return { console: updated };
    }),

  setCareGapState: (partial) =>
    set((state) => {
      const updated = { ...state.caregap, ...partial };
      const nextState = { ...state, caregap: updated };
      saveToSessionStorage(nextState);
      return { caregap: updated };
    }),

  setCoverageState: (partial) =>
    set((state) => {
      const updated = { ...state.coverage, ...partial };
      const nextState = { ...state, coverage: updated };
      saveToSessionStorage(nextState);
      return { coverage: updated };
    }),

  setMedTrendState: (partial) =>
    set((state) => {
      const updated = { ...state.medtrend, ...partial };
      const nextState = { ...state, medtrend: updated };
      saveToSessionStorage(nextState);
      return { medtrend: updated };
    }),

  setReportsState: (partial) =>
    set((state) => {
      const updated = { ...state.reports, ...partial };
      const nextState = { ...state, reports: updated };
      saveToSessionStorage(nextState);
      return { reports: updated };
    }),

  clearSession: () => {
    if (typeof window !== 'undefined') {
      try {
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
      } catch {}
    }
    set({
      console: initialConsole,
      caregap: initialCareGap,
      coverage: initialCoverage,
      medtrend: initialMedTrend,
      reports: initialReports,
    });
  },
}));
