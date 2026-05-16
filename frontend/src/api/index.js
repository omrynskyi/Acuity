import * as mock from './mock.js';
import * as real from './real.js';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const api = useMock ? mock : real;

export const analyzeRegimen = api.analyzeRegimen;
export const getSourceFindings = api.getSourceFindings;
export const streamAnalyzeRegimen = api.streamAnalyzeRegimen;
