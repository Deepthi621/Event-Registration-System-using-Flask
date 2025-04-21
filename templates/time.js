// Add this script to prevent time input errors
document.querySelector('input[name="start_time"]').addEventListener('change', function() {
    const endTime = document.querySelector('input[name="end_time"]');
    if (this.value >= endTime.value) {
        alert('End time must be after start time!');
        this.value = '';
    }
});

document.querySelector('input[name="end_time"]').addEventListener('change', function() {
    const startTime = document.querySelector('input[name="start_time"]');
    if (this.value <= startTime.value) {
        alert('End time must be after start time!');
        this.value = '';
    }
});