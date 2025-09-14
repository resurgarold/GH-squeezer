import mido
from collections import Counter, defaultdict
import random
import os
import glob
import math

def find_files():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    files = {}
    patterns = {
        'melod_mid': ["melod.mid", "melodyne.mid"],
        'melod_tempo': ["melod.tempo.mid", "melodyne.tempo.mid"],
        'solo_mid': ["solo.mid", "neural.mid", "neuralnote.mid"],
        'chord_mid': ["chord.mid", "chords.mid", "harmony.mid"]
    }
    
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            found = glob.glob(os.path.join(current_dir, pattern))
            if found:
                files[key] = found[0]
                break
        else:
            files[key] = None
    
    files['wav'] = glob.glob(os.path.join(current_dir, "*.wav"))
    files['mp3'] = glob.glob(os.path.join(current_dir, "*.mp3"))
    
    print(f"Найдено: MIDI({bool(files['melod_mid'])}), Tempo({bool(files['melod_tempo'])}), Neural({bool(files['solo_mid'])}), Chords({bool(files['chord_mid'])}), Audio({len(files['wav'])+len(files['mp3'])})")
    
    return (files['melod_mid'], files['melod_tempo'], files['solo_mid'], files['chord_mid'],
            files['wav'][0] if files['wav'] else None,
            files['mp3'][0] if files['mp3'] else None)

def extract_chord_progression(chord_file):
    if not chord_file:
        return None
    
    try:
        mid = mido.MidiFile(chord_file)
        chord_events = []
        
        for track in mid.tracks:
            current_time = 0
            active_chords = {}
            
            for msg in track:
                current_time += msg.time
                
                if hasattr(msg, 'note'):
                    if msg.type == 'note_on' and msg.velocity > 0:
                        active_chords[msg.note] = current_time
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in active_chords:
                            start_time = active_chords[msg.note]
                            chord_events.append((start_time, current_time, msg.note))
                            del active_chords[msg.note]
        
        chord_groups = defaultdict(list)
        for start, end, note in chord_events:
            chord_groups[start].append((note, end))
        
        chord_progression = []
        for start_time in sorted(chord_groups.keys()):
            notes = [note for note, end in chord_groups[start_time]]
            end_time = max(end for note, end in chord_groups[start_time])
            
            if len(notes) >= 2: 
                root_note = min(notes) % 12 
                chord_progression.append((start_time, end_time, root_note, notes))
        
        print(f"Гармонический анализ: {len(chord_progression)} аккордов")
        return chord_progression
        
    except Exception as e:
        print(f"Ошибка chord анализа: {e}")
        return None

def get_chord_at_time(chord_progression, time):
    if not chord_progression:
        return None
    
    for start, end, root, notes in chord_progression:
        if start <= time <= end:
            return root, notes
    return None

def create_harmonic_mapping(root_note):
    major_scale = [(root_note + offset) % 12 for offset in [0, 2, 4, 5, 7, 9, 11]]
    
    harmonic_map = {}
    for i, scale_note in enumerate(major_scale[:5]):
        harmonic_map[scale_note] = i
    
    return harmonic_map

def map_note_with_harmony(note, chord_progression, time, default_mapping):
    chord_info = get_chord_at_time(chord_progression, time)
    
    if chord_info:
        root_note, chord_notes = chord_info
        harmonic_map = create_harmonic_mapping(root_note)
        note_class = note % 12
        
        if note_class in harmonic_map:
            return harmonic_map[note_class]
    
    return default_mapping(note)

def extract_melodyne_skeleton(melod_mid, melod_tempo):
    if not melod_mid:
        return None
    
    try:
        mid = mido.MidiFile(melod_mid)
        print(f"Melodyne скелет: {os.path.basename(melod_mid)}")
        
        note_events = []
        for track_idx, track in enumerate(mid.tracks):
            current_time = 0
            for msg in track:
                current_time += msg.time
                if hasattr(msg, 'note') and msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                    note_events.append((current_time, msg.note, msg.velocity, msg.channel))
        
        note_events.sort()
        
        time_groups = defaultdict(list)
        for time, note, velocity, channel in note_events:
            time_groups[time].append((note, velocity, channel))
        
        cleaned_notes = []
        for time in sorted(time_groups.keys()):
            notes_at_time = time_groups[time]
            if len(notes_at_time) == 1:
                note, velocity, channel = notes_at_time[0]
                cleaned_notes.append((time, note, velocity, channel))
            else:
                best_note = max(notes_at_time, key=lambda x: x[1])
                note, velocity, channel = best_note
                cleaned_notes.append((time, note, velocity, channel))
        
        tempo_changes = []
        if melod_tempo:
            try:
                tempo_mid = mido.MidiFile(melod_tempo)
                for track in tempo_mid.tracks:
                    current_time = 0
                    for msg in track:
                        current_time += msg.time
                        if msg.type == 'set_tempo':
                            bpm = 60000000 / msg.tempo
                            tempo_changes.append((current_time, bpm, msg.tempo))
                print(f"Tempo: {len(tempo_changes)} изменений")
            except:
                pass
        
        if not tempo_changes:
            for track in mid.tracks:
                current_time = 0
                for msg in track:
                    current_time += msg.time
                    if msg.type == 'set_tempo':
                        bpm = 60000000 / msg.tempo
                        tempo_changes.append((current_time, bpm, msg.tempo))
        
        if not tempo_changes:
            tempo_changes = [(0, 120.0, 500000)]
        
        max_time = max(sum(msg.time for msg in track) for track in mid.tracks)
        
        print(f"Скелет: {len(cleaned_notes)} нот, {len(tempo_changes)} tempo")
        
        return {
            'notes': cleaned_notes,
            'tempo_changes': tempo_changes,
            'ticks_per_beat': mid.ticks_per_beat,
            'max_time': max_time
        }
        
    except Exception as e:
        print(f"Ошибка Melodyne: {e}")
        return None

def extract_neuralnote_notes(solo_mid):
    if not solo_mid:
        return None
    
    try:
        mid = mido.MidiFile(solo_mid)
        print(f"NeuralNote анализ: {os.path.basename(solo_mid)}")
        
        all_note_events = []
        for track_idx, track in enumerate(mid.tracks):
            current_time = 0
            for msg in track:
                current_time += msg.time
                if hasattr(msg, 'note') and msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                    all_note_events.append((current_time, msg.note, msg.velocity, msg.channel))
        
        all_note_events.sort()
        
        time_groups = defaultdict(list)
        for time, note, velocity, channel in all_note_events:
            time_groups[time].append((note, velocity, channel))
        
        cleaned_notes = []
        for time in sorted(time_groups.keys()):
            notes_at_time = time_groups[time]
            if len(notes_at_time) == 1:
                note, velocity, channel = notes_at_time[0]
                cleaned_notes.append((time, note, velocity, channel))
            else:
                sorted_by_velocity = sorted(notes_at_time, key=lambda x: x[1], reverse=True)
                top_loud = sorted_by_velocity[:min(3, len(sorted_by_velocity))]
                
                if len(top_loud) == 1:
                    best_note = top_loud[0]
                else:
                    notes_only = [note for note, vel, ch in top_loud]
                    center = (min(notes_only) + max(notes_only)) / 2
                    best_note = min(top_loud, key=lambda x: abs(x[0] - center))
                
                note, velocity, channel = best_note
                cleaned_notes.append((time, note, velocity, channel))
        
        if cleaned_notes:
            velocities = [vel for _, _, vel, _ in cleaned_notes]
            min_velocity = max(25, sum(velocities) / len(velocities) * 0.4)
            cleaned_notes = [(time, note, vel, ch) for time, note, vel, ch in cleaned_notes if vel >= min_velocity]
        
        print(f"Neural очистка: {len(all_note_events)} → {len(cleaned_notes)}")
        
        return {
            'notes': cleaned_notes,
            'ticks_per_beat': mid.ticks_per_beat
        }
        
    except Exception as e:
        print(f"Ошибка NeuralNote: {e}")
        return None

def calculate_safe_distance(melodyne_notes, ticks_per_beat):
    if len(melodyne_notes) < 2:
        return ticks_per_beat // 7
    
    intervals = []
    for i in range(1, len(melodyne_notes)):
        interval = melodyne_notes[i][0] - melodyne_notes[i-1][0]
        intervals.append(interval)
    
    avg_interval = sum(intervals) / len(intervals)
    fast_notes = sum(1 for interval in intervals if interval < ticks_per_beat // 4)
    fast_ratio = fast_notes / len(intervals)
    
    base_distance = min(avg_interval * 0.35, ticks_per_beat // 7)
    
    if fast_ratio > 0.3:
        safe_distance = base_distance * 2.0
    else:
        safe_distance = base_distance * 1.3
    
    safe_distance = max(ticks_per_beat // 14, min(safe_distance, ticks_per_beat // 3))
    
    return int(safe_distance)

def find_gaps_and_fill(melodyne_skeleton, neuralnote_notes):
    if not melodyne_skeleton or not neuralnote_notes:
        return []
    
    melodyne_notes = melodyne_skeleton['notes']
    neural_notes = neuralnote_notes['notes']
    ticks_per_beat = melodyne_skeleton['ticks_per_beat']
    
    print(f"Гибридный анализ: Melodyne({len(melodyne_notes)}) + Neural({len(neural_notes)})")
    
    safe_distance = calculate_safe_distance(melodyne_notes, ticks_per_beat)
    
    if neuralnote_notes['ticks_per_beat'] != ticks_per_beat:
        scale_factor = ticks_per_beat / neuralnote_notes['ticks_per_beat']
        neural_notes = [(int(time * scale_factor), note, vel, ch) for time, note, vel, ch in neural_notes]
    
    if melodyne_notes:
        melodyne_note_values = [note for _, note, _, _ in melodyne_notes]
        min_melodyne_note = min(melodyne_note_values)
        max_melodyne_note = max(melodyne_note_values)
        note_range_buffer = 8
    else:
        min_melodyne_note = 40
        max_melodyne_note = 80
        note_range_buffer = 8
    
    def is_safe_to_add(neural_time, neural_note):
        for melodyne_time, melodyne_note, _, _ in melodyne_notes:
            time_distance = abs(neural_time - melodyne_time)
            if time_distance < safe_distance:
                return False
        
        if neural_note < min_melodyne_note - note_range_buffer or neural_note > max_melodyne_note + note_range_buffer:
            return False
        
        return True
    
    added_notes = []
    for neural_time, neural_note, neural_vel, neural_ch in neural_notes:
        if is_safe_to_add(neural_time, neural_note):
            added_notes.append((neural_time, neural_note, neural_vel, neural_ch))
    
    combined_notes = melodyne_notes + added_notes
    combined_notes.sort()
    
    print(f"Гибрид готов: {len(combined_notes)} нот (+{len(added_notes)} из Neural)")
    
    return {
        'notes': combined_notes,
        'tempo_changes': melodyne_skeleton['tempo_changes'],
        'ticks_per_beat': ticks_per_beat,
        'max_time': melodyne_skeleton['max_time'],
        'added_count': len(added_notes),
        'skeleton_count': len(melodyne_notes)
    }
def process_hybrid_notes_with_harmony(hybrid_data, chord_progression):
    notes = hybrid_data['notes']
    if not notes:
        return []
    
    print(f"Гармоническая обработка: {len(notes)} нот")
        all_notes = [note for _, note, _, _ in notes]
    note_counts = Counter(all_notes)
    min_note = min(all_notes)
    max_note = max(all_notes)
    
    best_range_start = None
    best_count = 0
    
    for start in range(min_note, max_note - 4):
        count = sum(note_counts.get(start + i, 0) for i in range(5))
        if count > best_count:
            best_count = count
            best_range_start = start
    
    if not best_range_start:
        center = (min_note + max_note) // 2
        best_range_start = center - 2
    
    core_range = list(range(best_range_start, best_range_start + 5))
    
    def default_map_note_to_fret(note):
        if note in core_range:
            return core_range.index(note)
        elif note < best_range_start:
            distance = best_range_start - note
            return 0 if distance > 3 else 1
        else:
            distance = note - (best_range_start + 4)
            return 4 if distance > 3 else 3
    
    chart_notes = []
    ticks_per_beat = hybrid_data['ticks_per_beat']
    
    for i, (time, note, velocity, channel) in enumerate(notes):
        target_fret = map_note_with_harmony(note, chord_progression, time, default_map_note_to_fret)
        
        if chart_notes:
            prev_time, prev_fret = chart_notes[-1]
            
            if target_fret == prev_fret:
                alternatives = []
                if target_fret > 0:
                    alternatives.append(target_fret - 1)
                if target_fret < 4:
                    alternatives.append(target_fret + 1)
                if alternatives:
                    target_fret = random.choice(alternatives)
            
            elif i < len(notes) - 1:
                next_note = notes[i + 1]
                next_fret = map_note_with_harmony(next_note[1], chord_progression, next_note[0], default_map_note_to_fret)
                
                prev_gap = abs(target_fret - prev_fret)
                next_gap = abs(target_fret - next_fret)
                
                if prev_gap > 1 and next_gap > 1:
                    if target_fret == 0:
                        target_fret = 2
                    elif target_fret == 4:
                        target_fret = 3
                    elif target_fret == 1:
                        target_fret = 2
                    elif target_fret == 3:
                        target_fret = 2
        
        chart_notes.append((time, target_fret))
    
    final_notes = []
    
    for i, (time, fret) in enumerate(chart_notes):
        current_fret = fret
        
        if final_notes:
            prev_fret = final_notes[-1][1]
            gap = abs(current_fret - prev_fret)
            
            if gap > 2:
                if current_fret < prev_fret:
                    current_fret = max(current_fret, prev_fret - 2)
                else:
                    current_fret = min(current_fret, prev_fret + 2)
                current_fret = max(0, min(4, current_fret))
            
            if current_fret == prev_fret:
                if current_fret == 0:
                    current_fret = 1
                elif current_fret == 4:
                    current_fret = 3
                else:
                    current_fret = current_fret + (1 if random.random() > 0.5 else -1)
                    current_fret = max(0, min(4, current_fret))
        
        final_notes.append((time, current_fret))
    
    print(f"Chart готов: {len(final_notes)} нот")
    
    return final_notes

def calculate_difficulty(note_count, song_duration_seconds):
    if song_duration_seconds <= 0:
        return math.ceil(note_count / 100)
    
    notes_per_minute = (note_count / song_duration_seconds) * 60
    
    if notes_per_minute < 20:
        base_difficulty = 1
    elif notes_per_minute < 40:
        base_difficulty = 2
    elif notes_per_minute < 60:
        base_difficulty = 3
    elif notes_per_minute < 80:
        base_difficulty = 4
    elif notes_per_minute < 100:
        base_difficulty = 5
    elif notes_per_minute < 120:
        base_difficulty = 6
    elif notes_per_minute < 140:
        base_difficulty = 7
    elif notes_per_minute < 160:
        base_difficulty = 8
    else:
        base_difficulty = 9
    
    total_factor = 1.0
    if note_count > 500:
        total_factor = 1.2
    elif note_count < 200:
        total_factor = 0.8
    
    final_difficulty = max(1, min(10, int(base_difficulty * total_factor)))
    return final_difficulty

def generate_star_power_phrases(chart_notes, max_time):
    if not chart_notes:
        return []
    
    star_positions = []
    
    for percentage in [20, 40, 60, 80]:
        target_time = (max_time * percentage) // 100
        
        closest_note = None
        min_distance = float('inf')
        
        for time, fret in chart_notes:
            distance = abs(time - target_time)
            if distance < min_distance:
                min_distance = distance
                closest_note = (time, fret)
        
        if closest_note:
            note_time = closest_note[0]
            phrase_length = 8 * 4 * 192
            start_time = max(0, note_time - phrase_length // 2)
            end_time = note_time + phrase_length // 2
            
            star_positions.append((start_time, end_time))
    
    return star_positions

def create_harmonic_chart(hybrid_data, chart_notes, output_file, song_name, artist):
    ticks_per_beat = hybrid_data['ticks_per_beat']
    tempo_changes = hybrid_data['tempo_changes']
    max_time = hybrid_data['max_time']
    
    song_duration = hybrid_data.get('total_duration', 0)
    if not song_duration and hybrid_data.get('max_time'):
        tempo = hybrid_data['tempo_changes'][0][2] if hybrid_data['tempo_changes'] else 500000
        song_duration = (hybrid_data['max_time'] * tempo) / (hybrid_data['ticks_per_beat'] * 1000000)
    
    difficulty = calculate_difficulty(len(chart_notes), song_duration)
    star_phrases = generate_star_power_phrases(chart_notes, max_time)
    
    chart_content = f"""[Song]
{{
  Name = "{song_name}"
  Artist = "{artist}"
  Album = "Unknown Album"
  Year = ", 2025"
  Offset = 0
  Resolution = {ticks_per_beat}
  Player2 = bass
  Difficulty = {difficulty}
  PreviewStart = 0
  PreviewEnd = 0
  Genre = "rock"
  MediaType = "cd"
  MusicStream = "song.ogg"
}}

if __name__ == "__main__":
    main()

