// All modal surfaces share the document lock, including nested navigation dialogs.
let holders = 0;
let previousOverflow = '';
export function lockDialogScroll(): () => void {
    if (holders++ === 0) {
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
    }
    let released = false;
    return () => {
        if (released)
            return;
        released = true;
        if (--holders === 0)
            document.body.style.overflow = previousOverflow;
    };
}
