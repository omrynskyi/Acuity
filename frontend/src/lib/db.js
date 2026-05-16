import { supabase } from './supabase.js';

// ── Profile ───────────────────────────────────────────────────────────────────

export async function fetchProfile() {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data; // null if no profile exists yet
}

export async function updateProfileDoctor(profileId, doctor, doctorEmail) {
  const { error } = await supabase
    .from('profiles')
    .update({ doctor, doctor_email: doctorEmail })
    .eq('id', profileId);
  if (error) throw error;
}

export async function updateProfile(profileId, fields) {
  const { error } = await supabase
    .from('profiles')
    .update(fields)
    .eq('id', profileId);
  if (error) throw error;
}

export async function createProfile(userId, { name, age, sex, height, weight }) {
  const { data, error } = await supabase
    .from('profiles')
    .insert({
      user_id: userId,
      name,
      age,
      sex: sex || null,
      height: height || null,
      weight: weight || null,
      doctor: '',
      doctor_email: '',
    })
    .select()
    .single();
  if (error) throw error;
  return data;
}

// ── Regimen ───────────────────────────────────────────────────────────────────

export async function fetchRegimen(profileId) {
  const { data, error } = await supabase
    .from('regimen')
    .select('*')
    .eq('profile_id', profileId)
    .is('removed_at', null)
    .order('sort_order');
  if (error) throw error;
  return data;
}

export async function addDrugToRegimen(profileId, drug) {
  const { error } = await supabase.from('regimen').insert({
    profile_id:   profileId,
    input_name:   drug.input_name,
    rxcui:        drug.rxcui ?? null,
    generic_name: drug.generic_name ?? null,
    brand_names:  drug.brand_names ?? [],
    found:        drug.found ?? true,
    dose:         drug.dose ?? null,
    frequency:    drug.frequency ?? 'daily',
    sort_order:   drug.sort_order ?? 0,
  });
  if (error) throw error;
}

export async function updateRegimenDrug(regimenId, fields) {
  const { error } = await supabase
    .from('regimen')
    .update(fields)
    .eq('id', regimenId);
  if (error) throw error;
}

export async function removeDrugFromRegimen(regimenId) {
  const { error } = await supabase
    .from('regimen')
    .update({ removed_at: new Date().toISOString() })
    .eq('id', regimenId);
  if (error) throw error;
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export async function fetchRecentSessions(profileId, limit = 6) {
  const { data, error } = await supabase
    .from('sessions')
    .select('id, new_drug, generated_at, overall_severity, drugs_checked')
    .eq('profile_id', profileId)
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data;
}

export async function fetchSession(sessionId) {
  const { data, error } = await supabase
    .from('sessions')
    .select('report, new_drug, generated_at')
    .eq('id', sessionId)
    .single();
  if (error) throw error;
  return data;
}
