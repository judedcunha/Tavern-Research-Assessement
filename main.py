from wiki import get_page, find_short_path
import random
import warnings
import nltk
import spacy

def main():
    print("\n\n🥓 Welcome to WikiBacon! 🥓\n")
    print("In this game, we start from a random Wikipedia page, and then we compete to see who can name a page that is *farthest away* from the original page.\n")
    print("Ready to play? Hit Enter to start, or type 'q' to quit")
    cmd = input()
    if cmd == "q":
        return
    
    with open("dictionary.txt", "r") as f:
        common_words = f.read().splitlines()

    while True:

        start_page = None
        while start_page is None:
            start_word = random.choice(common_words)
            try:
                start_page = get_page(start_word)
            except Exception:
                continue
        print(f"The starting page is: {start_page.title}\n")
        print(f"Summary: {start_page.summary[:500]}...\n")

        computer_page = None
        while computer_page is None:
            computer_word = random.choice(common_words)
            try:
                computer_page = get_page(computer_word)
            except Exception:
                continue

        print(f"The computer's page is: {computer_page.title}\n")
        print(f"Summary: {computer_page.summary[:500]}...\n")

        print("What would you like your page to be?")
        user_page = None
        while user_page is None:
            user_page_name = input()
            try:
                user_page = get_page(user_page_name)
            except Exception:
                print(f"Could not find a Wikipedia page for '{user_page_name}'. Try another:")
        print(f"Your page is: {user_page.title}\n")
        print(f"Summary: {user_page.summary[:500]}...\n")

        print("Calculating Bacon paths...\n")

        computer_path = find_short_path(start_page, computer_page)
        print("Computer's path:")
        print(f"\n -> ".join(computer_path))
        print(f"Length: {len(computer_path)}\n")

        user_path = find_short_path(start_page, user_page)
        print("Your path:")
        print(f"\n -> ".join(user_path))
        print(f"Length: {len(user_path)}\n")

        if len(computer_path) > len(user_path):
            print("I win!")
        elif len(computer_path) < len(user_path):
            print("You win!")
        else:
            print("It's a tie!")

        print("\n\nPlay again? Hit Enter for another round, or type 'q' to quit")
        cmd = input()
        if cmd == "q":
            print("\n🥓 Thanks for playing! 🥓\n")
            print("WikiBacon is not affiliated with Wikipedia or the Wikimedia Foundation. To donate to Wikipedia and support their vision of an open internet that makes games like this possible, please visit https://donate.wikimedia.org/\n")
            return

if __name__ == "__main__":
    main()