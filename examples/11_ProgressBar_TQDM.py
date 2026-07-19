import tqdm
import time
import os

from ttytiles import TerminalTiler

# Create the TerminalTiler instance.
tt = TerminalTiler()

# Create a TerminalTiler progress bar.
pbar1 = tt.addProgressBar(
    x=1,
    y=3,
    width=tt.cols,
    barChar='█',
    max=100,
    textLeft="{PERCENT:3.0f}%|",
    textRight="| {VALUE}/{MAX} [{ELAPSED}<{REMAINING}, {AVG_ITTS:.2f}it/s] "
)

# Add labels identifying each progress bar.
labels = tt.addDisplayTile(
    x=1,
    y=1,
    width=tt.cols,
    height=8,
    textJust=TerminalTiler.Style.Justify.CENTERED
)
labels.set("TerminalTiler.ProgressBar\n\n\n\n\ntqdm")

# Create a standard tqdm progress bar for comparison.
with tqdm.tqdm(total=100) as pbar2:

    # Display the TerminalTiler progress bar.
    pbar1.show()

    # Update both progress bars simultaneously.
    for _ in range(100):
        time.sleep(0.05)

        # Advance the TerminalTiler progress bar.
        pbar1.update(1)

        # Move the cursor below the TerminalTiler UI so tqdm
        # renders on its own line instead of overwriting it.
        os.write(2, f"\033[{8};{1}H".encode())

        # Advance the tqdm progress bar.
        pbar2.update(1)

# Restore the terminal before exiting.
tt.close()