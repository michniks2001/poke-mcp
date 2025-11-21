// API base URL
const API_BASE = '/api';

// Helper function to show/hide elements
function showElement(id) {
    document.getElementById(id).style.display = 'block';
}

function hideElement(id) {
    document.getElementById(id).style.display = 'none';
}

// Helper function to display errors
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    showElement('error');
    hideElement('results');
}

// Helper function to clear errors
function clearError() {
    hideElement('error');
}

// Format team analysis results for display
function formatAnalysisResult(data) {
    let output = [];
    
    if (data.summary) {
        output.push('SUMMARY:');
        output.push(data.summary);
        output.push('');
    }
    
    if (data.llm_summary) {
        output.push('LLM SUMMARY:');
        output.push(data.llm_summary);
        output.push('');
    }
    
    if (data.threats && data.threats.length > 0) {
        output.push('THREATS:');
        data.threats.forEach(threat => {
            const pressure = threat.pressure || 0;
            const reasons = threat.reasons ? threat.reasons.join(', ') : 'No specific reasons';
            output.push(`  - ${threat.threat} (pressure: ${pressure.toFixed(2)})`);
            output.push(`    Reasons: ${reasons}`);
        });
        output.push('');
    }
    
    if (data.coverage_gaps && data.coverage_gaps.length > 0) {
        output.push('COVERAGE GAPS:');
        data.coverage_gaps.forEach(gap => {
            output.push(`  - ${gap}`);
        });
        output.push('');
    }
    
    if (data.recommendations && data.recommendations.length > 0) {
        output.push('RECOMMENDATIONS:');
        data.recommendations.forEach(rec => {
            output.push(`  - ${rec}`);
        });
        output.push('');
    }
    
    if (data.pokemon_insights && data.pokemon_insights.length > 0) {
        output.push('PER-POKEMON INSIGHTS:');
        data.pokemon_insights.forEach(insight => {
            const role = insight.role || 'Unknown role';
            const strengths = insight.strengths && insight.strengths.length > 0 
                ? insight.strengths.join(', ') 
                : 'No standout strengths';
            const risks = insight.risks && insight.risks.length > 0 
                ? insight.risks.join(', ') 
                : 'No major risks';
            output.push(`  - ${insight.pokemon}:`);
            output.push(`    Role: ${role}`);
            output.push(`    Strengths: ${strengths}`);
            output.push(`    Risks: ${risks}`);
            if (insight.speed_tier) {
                const st = insight.speed_tier;
                output.push(`    Speed Tier: Base ${st.base_speed}, Raw ${st.raw_speed}`);
                if (st.tailwind_speed) {
                    output.push(`      Tailwind Speed: ${st.tailwind_speed}`);
                }
                if (st.booster_speed) {
                    output.push(`      Booster Speed: ${st.booster_speed}`);
                }
                if (st.priority_moves && st.priority_moves.length > 0) {
                    output.push(`      Priority Moves: ${st.priority_moves.join(', ')}`);
                }
            }
        });
        output.push('');
    }
    
    if (data.speed_tiers && Object.keys(data.speed_tiers).length > 0) {
        output.push('SPEED TIER SUMMARY:');
        // Sort by raw speed
        const sortedTiers = Object.entries(data.speed_tiers)
            .sort((a, b) => (b[1].raw_speed || 0) - (a[1].raw_speed || 0));
        sortedTiers.forEach(([name, tier]) => {
            output.push(`  ${name}: ${tier.raw_speed} (Base: ${tier.base_speed})`);
            if (tier.tailwind_speed) {
                output.push(`    → Tailwind: ${tier.tailwind_speed}`);
            }
            if (tier.booster_speed) {
                output.push(`    → Booster: ${tier.booster_speed}`);
            }
            if (tier.priority_moves && tier.priority_moves.length > 0) {
                output.push(`    → Priority: ${tier.priority_moves.join(', ')}`);
            }
        });
        output.push('');
    }
    
    if (data.top_weaknesses && data.top_weaknesses.length > 0) {
        output.push('TOP WEAKNESSES:');
        data.top_weaknesses.forEach(weakness => {
            output.push(`  - ${weakness}`);
        });
        output.push('');
    }
    
    if (data.strategies && data.strategies.length > 0) {
        output.push('TEAM STRATEGIES:');
        data.strategies.forEach(strategy => {
            const confidence = (strategy.confidence * 100).toFixed(0);
            output.push(`  - ${strategy.name} (${strategy.category}, ${confidence}% confidence)`);
            output.push(`    ${strategy.summary}`);
            if (strategy.details && strategy.details.length > 0) {
                strategy.details.forEach(detail => {
                    output.push(`    • ${detail}`);
                });
            }
        });
        output.push('');
    }
    
    if (data.vector_context && data.vector_context.length > 0) {
        output.push('META SCOUTING:');
        data.vector_context.forEach(context => {
            const query = context.query || 'Similar meta Pokémon';
            const matches = context.matches || [];
            output.push(`  Query: ${query}`);
            matches.slice(0, 3).forEach(match => {
                const doc = match.document;
                if (typeof doc === 'string') {
                    try {
                        const info = JSON.parse(doc);
                        const name = info.name || 'Unknown';
                        const types = info.types ? info.types.join(', ') : '';
                        const typeContext = info.type_context || '';
                        output.push(`    - ${name} (${types})${typeContext ? ' - ' + typeContext : ''}`);
                    } catch (e) {
                        output.push(`    - ${doc.substring(0, 100)}...`);
                    }
                } else {
                    output.push(`    - ${String(doc).substring(0, 100)}...`);
                }
            });
            output.push('');
        });
    }
    
    return output.join('\n');
}

// Format parsed team for display
function formatParsedTeam(data) {
    let output = [];
    
    output.push('PARSED TEAM:');
    output.push(`Format: ${data.format || 'unknown'}`);
    if (data.name) {
        output.push(`Name: ${data.name}`);
    }
    output.push('');
    
    if (data.pokemon && data.pokemon.length > 0) {
        output.push(`Pokemon (${data.pokemon.length}):`);
        data.pokemon.forEach((pkmn, idx) => {
            output.push(`\n${idx + 1}. ${pkmn.name || 'Unknown'}`);
            if (pkmn.species) output.push(`   Species: ${pkmn.species}`);
            if (pkmn.item) output.push(`   Item: ${pkmn.item}`);
            if (pkmn.ability) output.push(`   Ability: ${pkmn.ability}`);
            if (pkmn.tera_type) output.push(`   Tera Type: ${pkmn.tera_type}`);
            if (pkmn.nature) output.push(`   Nature: ${pkmn.nature}`);
            if (pkmn.evs && Object.keys(pkmn.evs).length > 0) {
                output.push(`   EVs: ${JSON.stringify(pkmn.evs)}`);
            }
            if (pkmn.ivs && Object.keys(pkmn.ivs).length > 0) {
                output.push(`   IVs: ${JSON.stringify(pkmn.ivs)}`);
            }
            if (pkmn.moves && pkmn.moves.length > 0) {
                output.push(`   Moves: ${pkmn.moves.join(', ')}`);
            }
            if (pkmn.notes && pkmn.notes.length > 0) {
                output.push(`   Notes: ${pkmn.notes.join(', ')}`);
            }
        });
    } else {
        output.push('No Pokemon found in team.');
    }
    
    return output.join('\n');
}

// API call functions
async function parseTeam() {
    const teamText = document.getElementById('team-text').value.trim();
    
    if (!teamText) {
        showError('Please enter team text first.');
        return;
    }
    
    clearError();
    showElement('loading');
    hideElement('results');
    
    try {
        const response = await fetch(`${API_BASE}/parse_smogon_team`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ team_text: teamText }),
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const formatted = formatParsedTeam(data.result);
        
        document.getElementById('results').textContent = formatted;
        showElement('results');
    } catch (error) {
        showError(`Error parsing team: ${error.message}`);
    } finally {
        hideElement('loading');
    }
}

async function analyzeTeam() {
    const teamText = document.getElementById('team-text').value.trim();
    
    if (!teamText) {
        showError('Please enter team text first.');
        return;
    }
    
    clearError();
    showElement('loading');
    hideElement('results');
    
    try {
        const response = await fetch(`${API_BASE}/analyze_smogon_team`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ team_text: teamText }),
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const formatted = formatAnalysisResult(data.result);
        
        document.getElementById('results').textContent = formatted;
        showElement('results');
    } catch (error) {
        showError(`Error analyzing team: ${error.message}`);
    } finally {
        hideElement('loading');
    }
}

async function getPokemonData() {
    const species = document.getElementById('pokemon-species').value.trim();
    
    if (!species) {
        alert('Please enter a Pokemon species name.');
        return;
    }
    
    const utilityResults = document.getElementById('utility-results');
    utilityResults.textContent = 'Loading...';
    
    try {
        const response = await fetch(`${API_BASE}/get_pokemon_data?species=${encodeURIComponent(species)}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        utilityResults.textContent = data.result;
    } catch (error) {
        utilityResults.textContent = `Error: ${error.message}`;
    }
}

async function calculateTypeMatchup() {
    const attackerType = document.getElementById('attacker-type').value.trim();
    const defenderType = document.getElementById('defender-type').value.trim();
    
    if (!attackerType || !defenderType) {
        alert('Please enter both attacker and defender types.');
        return;
    }
    
    const utilityResults = document.getElementById('utility-results');
    utilityResults.textContent = 'Loading...';
    
    try {
        const response = await fetch(
            `${API_BASE}/calculate_type_matchup?attacker_type=${encodeURIComponent(attackerType)}&defender_type=${encodeURIComponent(defenderType)}`
        );
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        utilityResults.textContent = data.result;
    } catch (error) {
        utilityResults.textContent = `Error: ${error.message}`;
    }
}

function clearResults() {
    document.getElementById('team-text').value = '';
    document.getElementById('results').textContent = '';
    document.getElementById('utility-results').textContent = '';
    document.getElementById('pokemon-species').value = '';
    document.getElementById('attacker-type').value = '';
    document.getElementById('defender-type').value = '';
    clearError();
    hideElement('results');
}

// Allow Enter key to submit in utility inputs
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pokemon-species').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            getPokemonData();
        }
    });
    
    document.getElementById('attacker-type').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            calculateTypeMatchup();
        }
    });
    
    document.getElementById('defender-type').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            calculateTypeMatchup();
        }
    });
});

