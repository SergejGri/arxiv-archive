from connector import close_connection
from plots import plot_single_category

if __name__ == "__main__":
    try:
        plot_single_category(category="physics")

    finally:
        close_connection()
