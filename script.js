function loadVacations() {
  const stored = localStorage.getItem('vacations');
  return stored ? JSON.parse(stored) : [];
}

function saveVacations(vacations) {
  localStorage.setItem('vacations', JSON.stringify(vacations));
}

function renderVacations() {
  const tbody = document.querySelector('#vacation-table tbody');
  tbody.innerHTML = '';
  const vacations = loadVacations();
  vacations.forEach((vac, index) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${vac.employee}</td>
      <td>${vac.start}</td>
      <td>${vac.end}</td>
      <td><button class="delete-btn" data-index="${index}">Löschen</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function addVacation(vacation) {
  const vacations = loadVacations();
  vacations.push(vacation);
  saveVacations(vacations);
  renderVacations();
}

function deleteVacation(index) {
  const vacations = loadVacations();
  vacations.splice(index, 1);
  saveVacations(vacations);
  renderVacations();
}

document.getElementById('vacation-form').addEventListener('submit', function(e) {
  e.preventDefault();
  const employee = document.getElementById('employee').value.trim();
  const start = document.getElementById('start').value;
  const end = document.getElementById('end').value;
  if (employee && start && end) {
    addVacation({ employee, start, end });
    this.reset();
  }
});

document.querySelector('#vacation-table tbody').addEventListener('click', function(e) {
  if (e.target.classList.contains('delete-btn')) {
    const index = e.target.getAttribute('data-index');
    deleteVacation(index);
  }
});

window.addEventListener('load', renderVacations);
