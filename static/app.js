const poem = document.querySelector('#poem');
const count = document.querySelector('#word-count');
const fileInput = document.querySelector('#voice-file');
const generateButton = document.querySelector('#generate');
const notice = document.querySelector('#notice');
const styleSelect = document.querySelector('#style');
const customStyle = document.querySelector('#custom-style');
let pollTimer;

poem.addEventListener('input', () => {
  const words = poem.value.trim() ? poem.value.trim().split(/\s+/).length : 0;
  count.textContent = `${words} ${words === 1 ? 'word' : 'words'}`;
});
styleSelect.addEventListener('change', () => customStyle.classList.toggle('hidden', styleSelect.selectedIndex !== styleSelect.options.length - 1));
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  document.querySelector('#upload-main').textContent = file ? file.name : 'Choose a voice sample';
  document.querySelector('#upload-sub').textContent = file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to use` : 'WAV, MP3, M4A · up to 25 MB';
  document.querySelector('#upload-zone').classList.toggle('has-file', Boolean(file));
});
document.querySelector('#sample-poem').addEventListener('click', () => {
  const samples = [
    '[Verse 1]\nThe city folds its paper sky,\nAnd tucks the afternoon away.\nI find your laughter passing by,\nA little sun at end of day.\n\n[Chorus]\nStay a little, let the evening glow,\nThere are still a thousand things to know.\nIf the whole wide world should fade from view,\nI would find my way by finding you.',
    '[Verse 1]\nI left a window open wide,\nFor every wish I couldn’t say.\nThe stars came in and sat beside\nThe quiet parts I hid away.\n\n[Chorus]\nMaybe morning knows the way,\nMaybe light will learn to stay.\nTill the blue turns into gold,\nKeep my small hope safe to hold.',
    '[Verse 1]\nThere is a rhythm in the rain,\nA silver thread across the street.\nI hear the rooftops say your name,\nAnd tap it softly with their feet.\n\n[Chorus]\nLet it fall, let it sing,\nLet the night wear everything.\nIn the hush between the sounds,\nThat is where my heart is found.'
  ];
  poem.value = samples[Math.floor(Math.random() * samples.length)];
  poem.dispatchEvent(new Event('input'));
});

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle('error', isError);
  notice.classList.remove('hidden');
}
function setBusy(busy) {
  generateButton.disabled = busy;
  generateButton.querySelector('span:nth-child(2)').textContent = busy ? 'Making your song…' : 'Make my song';
  document.querySelector('#progress-wrap').classList.toggle('hidden', !busy);
  document.querySelector('#empty-player').classList.toggle('hidden', busy || !document.querySelector('#player-wrap').classList.contains('hidden'));
}
async function poll(taskId) {
  try {
    const response = await fetch('/api/status', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({task_id:taskId})});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Generation status unavailable.');
    if (data.status === 'succeeded') {
      clearInterval(pollTimer); setBusy(false);
      document.querySelector('#progress-wrap').classList.add('hidden');
      document.querySelector('#empty-player').classList.add('hidden');
      const audio = document.querySelector('#audio-player');
      audio.src = data.audio_url;
      document.querySelector('#download-link').href = data.audio_url;
      document.querySelector('#player-wrap').classList.remove('hidden');
      document.querySelector('#track-kicker').textContent = 'JUST MADE FOR YOU';
      document.querySelector('#track-title').textContent = 'Your poem, in song.';
      document.querySelector('#track-subtitle').textContent = 'A first take. Press play and listen in.';
      showNotice('Your song is ready. Use the player or download the MP3.');
    } else if (data.status === 'failed') throw new Error(data.error || 'The model could not finish this song.');
    else document.querySelector('#progress-message').textContent = data.status === 'queued' ? 'IN THE GENERATION QUEUE' : 'COMPOSING YOUR SONG';
  } catch (error) {
    clearInterval(pollTimer); setBusy(false); showNotice(error.message, true);
  }
}
generateButton.addEventListener('click', async () => {
  notice.classList.add('hidden');
  const lyrics = poem.value.trim();
  const voice = fileInput.files[0];
  if (!lyrics) return showNotice('Add a poem first, or use the poem inspiration button.', true);
  if (!voice) return showNotice('Choose a voice sample to guide the singing voice.', true);
  if (voice.size > 25 * 1024 * 1024) return showNotice('That file is over 25 MB. Choose a shorter sample.', true);
  const chosenStyle = styleSelect.value === '' && styleSelect.selectedIndex === styleSelect.options.length - 1 ? customStyle.value.trim() : styleSelect.value;
  if (styleSelect.selectedIndex === styleSelect.options.length - 1 && !chosenStyle) return showNotice('Describe the style you would like.', true);
  const form = new FormData();
  form.append('poem', lyrics); form.append('voice', voice); form.append('style', chosenStyle || 'Gentle indie folk, warm intimate lead vocal');
  setBusy(true); document.querySelector('#track-kicker').textContent = 'MAKING SOMETHING NEW';
  document.querySelector('#track-title').textContent = 'Your song is taking shape.';
  document.querySelector('#track-subtitle').textContent = 'The model is finding a melody for your words.';
  try {
    const response = await fetch('/api/generate', {method:'POST', body:form});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Could not start generation.');
    showNotice('Generation started. Keep this page open while ACE-Step works.');
    pollTimer = setInterval(() => poll(data.task_id), 3500);
    poll(data.task_id);
  } catch (error) { setBusy(false); showNotice(error.message, true); }
});

fetch('/api/health').then(r=>r.json()).then(state=>{
  const label=document.querySelector('#model-label');
  if(state.model==='online'){label.textContent='ACE-STEP CONNECTED';label.style.color='#667b5a';}
  else{label.textContent='MODEL OFFLINE';label.style.color='#a07857';}
}).catch(()=>{});
