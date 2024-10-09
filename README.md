# Medicus

Medicus is a Discord-bot with a couple of fun features

## See current and upcoming courses
Medicus allows students to see their current and upcoming courses in a Discord channel. All they need to do is link the correct ICS file to the channel.

## Verify students
Medicus allows students to verify that they're a KU Leuven student at the faculty of Medicine. This way we can ensure only Medicine students can access the full Discord server.

### How does verification work?
The Discord bot achieves this by using the user-provided `memberships.json` file. The file contains all students enrolled in certain courses. 
The user has to provide their e-mail address, Medicus checks if the e-mail is in the `memberships.json` file. If the e-mail is in the file, the verification process can continue.
The user receives a verification code in their e-mail. This verification code has to be provided to Medicus. If the verification code is correct, the user will be succesfully verified and will get access to all channels.
