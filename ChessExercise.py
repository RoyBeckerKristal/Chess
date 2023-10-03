from enum import Enum
import re
import copy
import tkinter
from tkinter import scrolledtext
import time
from threading import Timer
import socket
import random

num_rows = 8
num_cols = 8
last_byte_value = b'\xff'
annotation_byte_value = b'\xfe'
SERVER_ADDRESS = ('localhost',5000)


class Piece_type(Enum):
        NONE = 0
        KING = 1
        QUEEN = 2
        ROOK = 3
        BISHOP = 4
        KNIGHT = 5
        PAWN = 6

class Color(Enum):
        NONE = 0
        WHITE = 1
        BLACK = 2

class Status(Enum):
        NEW_GAME = 0
        GAME_ON = 1
        CHECKMATE = 2
        STALEMATE = 3
        REPEATED_MOVES = 4
        PASSIVITY = 5
        TIME_UP = 6
        NO_MATERIAL = 7
        RESIGNED = 8
        DRAW_OFFERED = 9
        DRAW_AGREED = 10

class Action(Enum):
        NONE = 0
        PLAY = 1
        OFFER = 2
        RESIGN = 3
        DUMMY = 4

def piece2symbol (pt, clr):
        if (not pt==Piece_type.NONE) and (not clr==Color.NONE):
                symbol = chr(9811 + (clr.value-1)*6 + pt.value)
                return symbol
        else:
                return ''
        

def run(sa):
        s = Match(sa)
        c1 = Client_match(sa)
        c2 = Client_match(ca)


# A virtual cell on the chess board
class Cell:
    #Cell attributes:        
    position = [0,0]                    #[row,column] position on the board
    is_occupied = False                 #is there a piece in the cell
    is_white_cell = False               #is the cell color on the board supposed to be white
    color = Color.NONE                  #color of the piece in the cell if occupied
    player = None                       #the player to whom the piece in the cell belongs
    piece = None                        #the piece in the cell if occupied
    piece_type = Piece_type.NONE        #type of piece in the cell if occupied
    board = None                        #the virtual board

    #Initializing the cell
    def __init__(self,board,row,column):
            #assigning the board and determining position on the board and whether the cell should appear white on the board
            self.board = board
            self.position = [row,column]
            self.is_white_cell = True if ((row%2)+column)%2 else False

    #Getting position in chess format ([0,5] => f1)    
    def get_position(self):
            return chr(self.position[1]+97) + chr(self.position[0]+49)

    #Updating the cell upon move into it / away from it
    def update(self, piece=None):
            #The cell is empty, setting its attributes accordingly
            if piece is None:
                    self.is_occupied = False
                    self.piece = None
                    self.color = Color.NONE
                    self.piece_type = Piece_type.NONE            
                    self.player = None
            #Otherwise, the cell is occupied, setting its attributes accordingly
            else:
                    self.is_occupied = True
                    self.piece = piece
                    self.player = piece.player
                    self.color = piece.player.color
                    self.piece_type = piece.piece_type

    #Printing a cell on the shell window for monitoring purposes
    def print_cell(self):
            import sys
            shell = sys.stdout.shell
            #Obtain the piece symbol
            symbol = self.piece.symbol if self.is_occupied else chr(8195)
            #Printing is done using one of four pre-determined IDLE formats, combining background (green/white) and text (black/gray)
            if self.is_white_cell:
                    bg = 'stdout' if self.color==Color.WHITE else ''
            else:
                    bg = 'stderr' if self.color==Color.WHITE else 'KEYWORD'
            a = shell.write(symbol,bg)


# A virtual chessboard
class Board:
    #Board attributes
    cells = []          # The cells on the board

    #Creating an empty chess board
    def __init__(self):
            self.cells = [[Cell(self,r,c) for c in range(num_cols)] for r in range(num_rows)]

    #Returning an integer number as a unique key for any situation on the board
    def position_to_int(self):
            key = 0     #The integer key to be returned
            #Iterating through the cells in the rows and columns on the board
            for r in range (num_rows):
                    for c in range (num_cols):
                            #Obtaining the serial integer for the current cell based on row and column (0-63)
                            cell_key = r*num_cols+c
                            #Obtaining the integer for the piece in the current cell based on piece type and color (0-12) 
                            position_key = (self.cells[r][c].color.value-1)*6+self.cells[r][c].piece_type.value if self.cells[r][c].is_occupied else 0
                            #Combining cell and piece information into a unique number as a power for base 13, and adding it to the cumulative key
                            key += 13**cell_key*position_key
            #Returning the key
            return key        

    #Printing a board on the shell window for monitoring purposes           
    def print_board(self):
            #Printing column letters above
            print(' '+chr(65313)+chr(65314)+chr(65315)+chr(65316)+chr(65317)+chr(65318)+chr(65319)+chr(65320))
            #Iterating through rows backwards because white is at bottom
            for r in range(num_rows-1,-1,-1):
                    #Printing row number
                    print(r+1,end='')
                    #Iterating through cells in the row
                    for c in range(num_cols):
                            #Printing cell
                            self.cells[r][c].print_cell()
                    #Printing row number again
                    print(r+1)
            #Printing column letters below
            print(' '+chr(65313)+chr(65314)+chr(65315)+chr(65316)+chr(65317)+chr(65318)+chr(65319)+chr(65320))


# A virtual piece in a cell on the board
class Piece:
    #Piece attributes:
    piece_type = Piece_type.NONE        #Piece type (king, pawn, etc...)
    color = Color.NONE                  #Piece color (white/black)
    symbol = None                       #Piece symbol (character) according to type for printing
    player = None                       #Player to which the piece belongs
    is_king = False                     #Is it the king piece - needed for special king-related behavior
    current_cell = None                 #The cell the piece currently occupies
    has_moved = False                   #Whether or not the piece has moved from its initial position
    en_passant = False                  #Can this piece (pawn) be captured en passant
    target_cells = []                   #The cells currently covered by the potential movements of the piece
    move_cells = []                     #The cells the piece can actually move to (depening on turn, king exposure etc.)

    #Initializing the piece
    def __init__ (self,piece_type,player,cell,symbol=None):
            #Assigning its attributes
            self.piece_type = piece_type
            self.is_king = True if piece_type==Piece_type.KING else False
            self.player = player
            self.color = self.player.color
            self.current_cell = cell
            self.symbol = symbol
            self.has_moved = False
            #Updating the cell the piece occupies
            self.current_cell.update(self)
            
    #Moving the piece to a cell
    def move(self,next_cell):
            #Clearly the piece has now moved from its original position
            self.has_moved = True
            #Updating the emptied cell
            self.current_cell.update()
            #If moving to an occupied cell (capturing an opponent piece)...
            if next_cell.is_occupied:
                    #...the opponent removes the piece
                    next_cell.player.remove_piece(next_cell.piece)
            #Assigning the piece's new cell
            self.current_cell = next_cell
            #Updating the cell with its new occupant piece
            next_cell.update(self)
            #Movement under Check relieves player from Check
            if self.player.checked:
                    self.player.checked = False

    #Updating the cells associated with piece movement
    def update_cells(self):
            #If piece is attacking the opponent's king...
            if self.player.opponent.king.current_cell in self.target_cells:
                    #...opponent is checked, and the piece is among the attacking pieces
                    self.player.opponent.checked = True
                    self.player.checking_pieces.append(self)

            #If it's the opponent's turn then the piece can't move
            if not self.player.my_turn:
                    self.move_cells.clear()
            #If it's the piece's player's turn...
            else:
                    friendly_cells = [] #cells in the range of the current piece occupied by fellow pieces of the player
                    safe_cells = []     #cells safe for king's movement
                    
                    #Identifying all the friendly cells, to be excluded from the set of cells the piece can move into
                    for tc in self.target_cells:
                            if tc.is_occupied and tc.color==self.color:
                                    friendly_cells.append(tc)
                    
                    #Identifying all the safe cells, as follows...
                    #If the current piece is the king itself...
                    if self.piece_type==Piece_type.KING:
                            kp = self.current_cell.position     #king's position
                            #Running through the king's target cells....
                            for tc in self.target_cells:
                                    #If the target cell is not attacked by the opponent, it's safe in principle.
                                    if not tc in self.player.opponent.all_target_cells:
                                            safe_cells.append(tc)
                                            #But if the king is under attack...
                                            if self.player.checked:
                                                    #...castling (the only horizontal two-cell movement) is forbidden so the move isn't regarded as safe...
                                                    if abs(tc.position[1]-kp[1])==2 and tc in safe_cells:
                                                            safe_cells.remove(tc)
                                                    #Regarding non-castling targets...
                                                    else:
                                                            #...running through the opponent's attacking pieces...
                                                            for cp in self.player.opponent.checking_pieces:
                                                                    #...and if current attacking piece is a 'long distance attacker'....
                                                                    if cp.piece_type==Piece_type.QUEEN or cp.piece_type==Piece_type.ROOK or cp.piece_type==Piece_type.BISHOP:
                                                                            #...then the king cannot escape attack by moving away from the attacker on the attack path, as follows...
                                                                            ap = cp.current_cell.position #attacker position
                                                                            #...figuring out the nature of the direct path between the attacker and the king, and defining what a step away means...
                                                                            vstep = (ap[0]-kp[0])//abs(ap[0]-kp[0]) if not kp[0]==ap[0] else 0
                                                                            hstep = (ap[1]-kp[1])//abs(ap[1]-kp[1]) if not kp[1]==ap[1] else 0
                                                                            #...identifying the cell which is one step away along the path...
                                                                            nvp = kp[0]-vstep
                                                                            nhp = kp[1]-hstep
                                                                            #... and if this is indeed a cell on the board...
                                                                            if nvp>-1 and nvp<8 and nhp>-1 and nhp<8:
                                                                                    np = self.player.board.cells[nvp][nhp]
                                                                                    if np in safe_cells:        #10
                                                                                            #...it cannot be regarded safe
                                                                                            safe_cells.remove(np)
                            #Now that all king's target cells were evaluated for safety, there's the case of castling when there's no attack, if the intermediate cell is unsafe...
                            if not self.has_moved:  #3
                                    kscc = self.player.board.cells[kp[0]][6]    #king side castling cell
                                    kscic = self.player.board.cells[kp[0]][5]   #king side castling intermediate cell
                                    #If the intermediate cell isn't safe, then the castling cell isn't safe either, hence removed
                                    if (kscc in safe_cells) and (not kscic in safe_cells):
                                            safe_cells.remove(kscc)
                                    qscc = self.player.board.cells[kp[0]][2]    #queen side castling cell
                                    qscic = self.player.board.cells[kp[0]][3]   #queen side castling intermediate cell
                                    #If the intermediate cell isn't safe, then the castling cell isn't safe either, hence removed
                                    if (qscc in safe_cells) and (not qscic in safe_cells):
                                            safe_cells.remove(qscc)
                            #The king move cells are the subset of safe target cells that aren't friendly cells
                            self.move_cells = [sc for sc in safe_cells if not sc in friendly_cells]
                            return
                    #Now to the case where the current piece is not the king - it can't move if the result is attack on its king
                    else:
                            kp = self.player.king.current_cell.position #king's position
                            pp = self.current_cell.position             #current piece's position
                            exposure_relevant = False                   #is king exposure upon piece movement relevant? false by default

                            #Exposure may turn up relevant only if the king and the piece are on the movement line of a long distance attacker...
                            if (kp[0]==pp[0]) or (kp[1]==pp[1]) or (abs(pp[0]-kp[0])==abs(pp[1]-kp[1])):
                                    #...in which case, steps along the line are defined
                                    vstep = (pp[0]-kp[0])//abs(pp[0]-kp[0]) if not kp[0]==pp[0] else 0
                                    hstep = (pp[1]-kp[1])//abs(pp[1]-kp[1]) if not kp[1]==pp[1] else 0
                                    cp = [kp[0]+vstep,kp[1]+hstep] #a position along the potential attack line adjacent to the king
                                    passed_piece = False #whether the position is beyond the current (potentially protective) piece or not
                                    sequence_cells = []
                                    #Running through positions on the potential attack line on the board...
                                    while cp[0]>-1 and cp[0]<8 and cp[1]>-1 and cp[1]<8:
                                            cc = self.player.board.cells[cp[0]][cp[1]] #The cell in the current position
                                            #If the cell is occupied, then...
                                            if cc.is_occupied:
                                                    #...if the current piece hasn't been reached yet...
                                                    if not passed_piece:
                                                            #...if it's not the current piece then this piece isn't protective
                                                            if not cp==self.current_cell.position:
                                                                    break
                                                            #...if it is the current piece, then it has been reached.
                                                            else:
                                                                    passed_piece = True
                                                    #...if the current piece is beyond the protective piece...
                                                    else:
                                                            #...if it belongs to the same player as the king and the piece, then the intervening piece isn't protective
                                                            if cc.piece.color==self.color:
                                                                    break
                                                            #...if it belongs to the opponent, and is a long distance attacker matching the path type...
                                                            elif cc.piece.piece_type==Piece_type.QUEEN or ((vstep==0 or hstep==0) and cc.piece.piece_type==Piece_type.ROOK) \
                                                            or (not (vstep==0 or hstep==0) and cc.piece.piece_type==Piece_type.BISHOP):
                                                                    #...then the current (intervening) piece is indeed protective, i.e. exposure IS relevant
                                                                    exposure_relevant = True
                                                                    #...and the attacker's cell is among the only permitted movements of the protective piece
                                                                    sequence_cells.append(cc)
                                                                    break
                                            #If the cell isn't occupied, then it's among the permitted movements of the potentially protective piece
                                            else:
                                                    sequence_cells.append(cc)
                                            #moving to the next position along the potential attack line
                                            cp = [cp[0]+vstep,cp[1]+hstep]
                            #If exposure is relevant...
                            if exposure_relevant:
                                    #... then the safe cells are only the piece's target cells that were found to be on the path between the attacker and the king
                                    safe_cells = [tc for tc in self.target_cells if tc in sequence_cells]
                            #If exposure isn't relevant then all target cells are safe
                            else:
                                    safe_cells = self.target_cells
                            #If the king is under attack... 
                            if self.player.checked:
                                    #...the piece may only move to a protective cell to counter the attack as follows...
                                    opponent = self.player.opponent
                                    #only king can move if doubly-attacked
                                    if len(opponent.checking_pieces)>1:
                                            return
                                    #But if there's only one attacking piece...
                                    #If it's a short-distance attacker, then the only protection is by capturing the attacker
                                    elif opponent.checking_pieces[0].piece_type==Piece_type.PAWN or opponent.checking_pieces[0].piece_type==Piece_type.KNIGHT:
                                            attacking_cell = opponent.checking_pieces[0].current_cell
                                            #Capturing the attacker is permitted only if the movement is safe, i.e. not exposing the king elsewhere
                                            self.move_cells = [attacking_cell] if attacking_cell in safe_cells else []
                                            return
                                    #If it's a long-distance attacker...
                                    else:
                                            ap = opponent.checking_pieces[0].current_cell.position      #attacking piece position
                                            kp = self.player.king.current_cell.position         #attacked piece position
                                            #Defining step on attack path
                                            vstep = (ap[0]-kp[0])//abs(ap[0]-kp[0]) if not ap[0]==kp[0] else 0
                                            hstep = (ap[1]-kp[1])//abs(ap[1]-kp[1]) if not ap[1]==kp[1] else 0
                                            #Cells along the path between attacker and king are protective
                                            protective_cells = []
                                            reached_attacker = False    #has attacker been reached?
                                            cp = [kp[0]+vstep,kp[1]+hstep]      #current position starting next to the attacked king
                                            #Running through cells from king to attacker
                                            while not reached_attacker:
                                                    if cp==ap:
                                                            reached_attacker = True
                                                    cc = self.player.board.cells[cp[0]][cp[1]]
                                                    #If movement to the current cell doesn't expose the king elsewhere...
                                                    if cc in safe_cells:
                                                            #...then this cell is protective
                                                            protective_cells.append(cc)
                                                    #Identifying the next cell to examine
                                                    cp = [cp[0]+vstep,cp[1]+hstep]
                                    #So.. if the king is attacked, the piece can move only to the cells identified as protective
                                    self.move_cells = protective_cells
                                    return
                            #If the king isn't under attack...
                            else:
                                    #if self.piece_type==Piece_type.PAWN:
                                    #        empty_capture_cells = []
                                    #        pp = self.current_cell.position
                                    #        r = pp[0]
                                    #        c = pp[1]
                                    #        nr = r+1 if self.color==Color.WHITE else r-1
                                    #        epr = 4 if self.color==Color.WHITE else 3
                                    #        print(r,c,nr,c-1,self.player.board.cells[nr][c-1].is_occupied,r==epr,self.player.board.cells[r][c-1].is_occupied,end=" ")
                                    #        if self.player.board.cells[r][c-1].is_occupied:
                                    #                print(self.player.board.cells[r][c-1].piece.en_passant)
                                    #        else:
                                    #                print()
                                    #        if c>0 and r>0 and r<7 and (not self.player.board.cells[nr][c-1].is_occupied) and \
                                    #        (not (r==epr and self.player.board.cells[r][c-1].is_occupied and self.player.board.cells[r][c-1].piece.en_passant)):
                                    #                empty_capture_cells.append(self.player.board.cells[nr][c-1])
                                    #        if c<7 and r>0 and r<7 and (not self.player.board.cells[nr][c+1].is_occupied) and \
                                    #        (not (r==epr and self.player.board.cells[r][c+1].is_occupied and self.player.board.cells[r][c+1].piece.en_passant)):
                                    #                empty_capture_cells.append(self.player.board.cells[nr][c+1])
                                    #        self.move_cells = [sc for sc in safe_cells if (not sc in friendly_cells) and (not sc in empty_capture_cells)]
                                    #        for mc in self.move_cells:
                                    #                print(mc.get_position(),end=" ")
                                    #        print()
                                    #else:
                                            #... then the piece can move to all target cells as long as the king isn't exposed and those cells aren't occupied by fellow pieces
                                    self.move_cells = [sc for sc in safe_cells if not sc in friendly_cells]
                                    #return
                
                            
# A virtual pawn is a subclass of Piece
class Pawn(Piece):
    capture_cells = []    
    #Initializing a pawn
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9817) if player.color==Color.WHITE else chr(9823)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.PAWN,player,cell,self.symbol)
            
    #Defining the basic range of cells covered by the pawn according to the rules
    def update_cells(self):
            target_cells = []       #The set of target cells
            capture_cells = []
            #Pawn movement is only forward away from the back row
            if self.color == Color.WHITE:
                    back_row = 0
                    step = 1
            else:
                    back_row = 7
                    step = -1
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #If reached opponent edge there are no target cells (pawn promotion instead)
            if row==7-back_row:
                    return
            next_cell = self.player.board.cells[row+step][col]  #Cell immediately in front of the pawn
            #Adding the cell immediately in front as target cell if it's not occupied 
            if not next_cell.is_occupied:
                    target_cells.append(next_cell)
                    #If the pawn hasn't moved yet, adding also the cell two rows ahead if free
                    if not self.has_moved:
                            yonder_cell = self.player.board.cells[row+step*2][col]
                            if not yonder_cell.is_occupied:
                                    target_cells.append(yonder_cell)
            #If pawn isn't on left-most column, adding the cell immediately at front-left if occupied
            if col>0:
                    strike_left_cell = self.player.board.cells[row+step][col-1]
                    target_cells.append(strike_left_cell)
                    capture_cells.append(strike_left_cell)
            #If pawn isn't on right-most column, adding the cell immediately at front-right if occupied
            if col<7:
                    strike_right_cell = self.player.board.cells[row+step][col+1]
                    target_cells.append(strike_right_cell)
                    capture_cells.append(strike_right_cell)
#            #If on fifth row checking condition for en-passant capture
#            if row==back_row+step*4:
#                    # If not on left-most column...
#                    if col>0:
#                            #...identifying cell immediately to the left for potential en-passant capture
#                            strike_en_passant_left_cell = self.player.board.cells[row][col-1]
#                            #If this cell is occupied by an en-passant piece (an opponent pawn just moved into the cell)...
#                            if strike_en_passant_left_cell.is_occupied and strike_en_passant_left_cell.piece.en_passant:
#                                    #...the cell immediately behind the en-passant piece is identified as a target cell and added
#                                    strike_left_cell = self.player.board.cells[row+step][col-1]
#                                    target_cells.append(strike_left_cell)
#                    # If not on right-most column...
#                    if col<7:
#                            #...identifying cell immediately to the right for potential en-passant capture
#                            strike_en_passant_right_cell = self.player.board.cells[row][col+1]
#                            #If this cell is occupied by an en-passant piece (an opponent pawn just moved into the cell)...
#                            if strike_en_passant_right_cell.is_occupied and strike_en_passant_right_cell.piece.en_passant:
#                                    #...the cell immediately behind the en-passant piece is identified as a target cell and added
#                                    strike_right_cell = self.player.board.cells[row+step][col+1]
#                                    target_cells.append(strike_right_cell)
            #Assigning the set of target cells to the pawn piece object...
            self.target_cells = target_cells
            self.capture_cells = capture_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)
            move_cells = self.move_cells
            remove_cells = []
            if move_cells:
                    for mc in move_cells:
                            if mc in self.capture_cells and (not mc.is_occupied) and (not (self.player.board.cells[row][mc.position[1]].is_occupied and self.player.board.cells[row][mc.position[1]].piece.en_passant)):
                                    remove_cells.append(mc)
                    self.move_cells = [mc for mc in move_cells if not mc in remove_cells]

    #Pawn movement to the specified cell
    def move(self,next_cell):
            #if moving to a cell on a different column, i.e. capturing a piece...
            if not next_cell.position[1]==self.current_cell.position[1]:
                    #...identifying en-passant cell at the same row as the pawn and same column as the target cell, just in case this move is en-passant capture
                    ic = self.player.board.cells[self.current_cell.position[0]][next_cell.position[1]]
                    #If this is indeed en-passant capture...
                    if ic.is_occupied and ic.piece.en_passant:
                            #...first capturing the en-passant pawn and then moving to the cell beyond it
                            Piece.move(self,ic)
                            Piece.move(self,next_cell)
                    #If it's normal capture, simply moving in.
                    else:
                            Piece.move(self,next_cell)
            #If moving forward on the column, i.e. not capturing a piece...
            else:
                    #...if this is a first, double move of the pawn...
                    if not self.has_moved and abs(next_cell.position[0]-self.current_cell.position[0])==2:
                            #...assigning the pawn as an en-passant piece for the opponent's next move
                            self.en_passant = True
                            self.player.en_passant_piece = self
                    #Moving the pawn to the cell
                    Piece.move(self,next_cell)
                    if not self.player.en_passant_piece is None:
                            print(self.player.en_passant_piece.current_cell.get_position(), self.player.en_passant_piece.en_passant)
                            

# A virtual knight is a subclass of Piece
class Knight(Piece):
        
    #Initializing a knight
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9816) if player.color==Color.WHITE else chr(9822)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.KNIGHT,player,cell,self.symbol)

    #Defining the basic range of cells covered by the knight according to the rules        
    def update_cells(self):
            target_cells = []   #The set of target cells
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #Now defining the list of eight (theoretical) positions comprising a circle of cells around the knight reached by knight moves
            target_circle = [[row-2,col-1],[row-1,col-2],[row+1,col-2],[row+2,col-1],[row+2,col+1],[row+1,col+2],[row-1,col+2],[row-2,col+1]]
            #Going through each of the theoretical positions
            for tp in target_circle:
                    #If the current position is within the board limits...
                    if tp[0]>-1 and tp[0]<8 and tp[1]>-1 and tp[1]<8:
                            #...obtaining its cell and adding it to the set of target cells
                            target_cell = self.player.board.cells[tp[0]][tp[1]]
                            target_cells.append(target_cell)
            #Assigning the set of target cells to the knight piece object...
            self.target_cells = target_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)


# A virtual bishop is a subclass of Piece
class Bishop(Piece):

    #Initializing a bishop        
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9815) if player.color==Color.WHITE else chr(9821)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.BISHOP,player,cell,self.symbol)

    #Defining the basic range of cells covered by the bishop according to the rules                    
    def update_cells(self):
            target_cells = []   #The set of target cells
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #Defining the steps in all four diagonal directions
            steps = [[-1,-1],[-1,1],[1,1],[1,-1]]
            #Going through each of the four diagonal paths
            for s in steps:
                    blocked = False     #Whether a piece is encountered
                    r = row     #Row counter starting at the current bishop position
                    c = col     #Column counter starting at the current bishop position
                    # As long as no piece is encountered...
                    while not blocked:
                            #...identifying the coordinates of the next cell on the path
                            r = r+s[0]
                            c = c+s[1]
                            #If this cell is within board boundaries...
                            if r>-1 and r<8 and c>-1 and c<8:
                                    #...adding this cell to the set of target cells
                                    target_cell = self.player.board.cells[r][c]
                                    target_cells.append(target_cell)
                                    #If a piece is occupied, then the search on this path is done
                                    if target_cell.is_occupied:
                                            blocked = True
                            #If the path reached the board boundaries, the search is done
                            else:
                                    blocked = True
            #Assigning the set of target cells to the bishop piece object...
            self.target_cells = target_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)
    

# A virtual rook is a subclass of Piece
class Rook(Piece):

    #Initializing a rook
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9814) if player.color==Color.WHITE else chr(9820)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.ROOK,player,cell,self.symbol)

    #Defining the basic range of cells covered by the rook according to the rules 
    def update_cells(self):
            target_cells = []   #The set of target cells
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #Defining the steps in all four straight directions
            steps = [[-1,0],[0,-1],[1,0],[0,1]]
            #Going through each of the four straight paths
            for s in steps:
                    blocked = False     #Whether a piece is encountered
                    r = row     #Row counter starting at the current bishop position
                    c = col     #Column counter starting at the current bishop position
                    # As long as no piece is encountered...
                    while not blocked:
                            #...identifying the coordinates of the next cell on the path
                            r = r+s[0]
                            c = c+s[1]
                            #If this cell is within board boundaries...
                            if r>-1 and r<8 and c>-1 and c<8:
                                    #...adding this cell to the set of target cells
                                    target_cell = self.player.board.cells[r][c]
                                    target_cells.append(target_cell)
                                    #If a piece is occupied, then the search on this path is done
                                    if target_cell.is_occupied:
                                            blocked = True
                            #If the path reached the board boundaries, the search is done
                            else:
                                    blocked = True
            #Assigning the set of target cells to the rook piece object...
            self.target_cells = target_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)


# A virtual queen is a subclass of Piece    
class Queen(Piece):

    #Initializing a queen
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9813) if player.color==Color.WHITE else chr(9819)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.QUEEN,player,cell,self.symbol)

    #Defining the basic range of cells covered by the queen according to the rules             
    def update_cells(self):
            target_cells = []   #The set of target cells
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #Defining the steps in all eight directions
            steps = [[-1,-1],[0,-1],[1,-1],[1,0],[1,1],[0,1],[-1,1],[-1,0]]
            #Going through each of the eight paths
            for s in steps:
                    blocked = False     #Whether a piece is encountered
                    r = row     #Row counter starting at the current bishop position
                    c = col     #Column counter starting at the current bishop position
                    # As long as no piece is encountered...
                    while not blocked:
                            #...identifying the coordinates of the next cell on the path
                            r = r+s[0]
                            c = c+s[1]
                            #If this cell is within board boundaries...
                            if r>-1 and r<8 and c>-1 and c<8:
                                    #...adding this cell to the set of target cells
                                    target_cell = self.player.board.cells[r][c]
                                    target_cells.append(target_cell)
                                    #If a piece is occupied, then the search on this path is done
                                    if target_cell.is_occupied:
                                            blocked = True
                            #If the path reached the board boundaries, the search is done
                            else:
                                    blocked = True
            #Assigning the set of target cells to the queen piece object...
            self.target_cells = target_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)


# A virtual king is a subclass of Piece    
class King(Piece):

    #Initializing a king        
    def __init__(self,player,cell):
            #Assigning its symbol
            self.symbol = chr(9812) if player.color==Color.WHITE else chr(9818)
            #Initializing the embedded Piece
            Piece.__init__(self,Piece_type.KING,player,cell,self.symbol)

    #Defining the basic range of cells covered by the king according to the rules             
    def update_cells(self):        
            target_cells = []   #The set of target cells
            row = self.current_cell.position[0] #Row of current cell
            col = self.current_cell.position[1] #Column of current cell
            #Now defining the list of eight (theoretical) positions comprising a circle of cells immediately around the king piece
            target_circle = [[row-1,col-1],[row,col-1],[row+1,col-1],[row+1,col],[row+1,col+1],[row,col+1],[row-1,col+1],[row-1,col]]
            #Going through all eight positions
            for tp in target_circle:
                    #if the position is within the board boundaries...
                    if tp[0]>-1 and tp[0]<8 and tp[1]>-1 and tp[1]<8:
                            #...adding the cell to the set of target cells
                            target_cells.append(self.player.board.cells[tp[0]][tp[1]])
            #Castling: if the king never moved...
            if not self.has_moved:
                    #...identifying the king's row
                    row_cells = self.player.board.cells[row]
                    #If the two cells between the king and the king side rook are vacant...
                    if row_cells[7].is_occupied and (not row_cells[7].piece.has_moved) and (not row_cells[6].is_occupied) and (not row_cells[5].is_occupied):
                            #...adding the cell two steps away from the king on the king side to the target cells
                            target_cells.append(row_cells[6])
                    #If the three cells between the king and the queen side rook are vacant...
                    if row_cells[0].is_occupied and (not row_cells[0].piece.has_moved) and (not row_cells[1].is_occupied) and (not row_cells[2].is_occupied) and (not row_cells[3].is_occupied):
                            #...adding the cell two steps away from the king on the queen side to the target cells
                            target_cells.append(row_cells[2])
            #Assigning the set of target cells to the queen piece object...
            self.target_cells = target_cells
            #...and now further processing it by generic validation of movement
            Piece.update_cells(self)

    #Defining king move
    def move(self,next_cell):
            #If king hasn't moved yet and it's a two-step horizontal move (castling)
            if not self.has_moved and (next_cell.position[1]==6 or next_cell.position[1]==2):
                    #defining direction of movement
                    step = 1 if next_cell.position[1]==6 else -1
                    #Identifying the relevant rook column
                    rook_column = 7 if next_cell.position[1]==6 else 0
                    #Identifying the target cell of the rook movement
                    rook_cell = self.player.board.cells[self.current_cell.position[0]][4+step]
                    #Moving the king
                    Piece.move(self,next_cell)
                    #Obtaining the rook
                    rook = self.player.board.cells[self.current_cell.position[0]][rook_column].piece
                    #Moving the rook beyond the moved king
                    rook.move(rook_cell)
            #If not castling, normal move of the king
            else:
                    Piece.move(self,next_cell)
                

# A virtual player or side on a chess game        
class Player:
    pieces = None       #The player's set of pieces
    color = Color.NONE  #The player's color
    board = None        #The match board
    opponent = None     #The other player
    en_passant_piece = None     #The pawn that can now be captured en-passant, if any
    all_target_cells = None     #All board cells covered by possible moves of the player's pieces
    all_move_cells = None       #All cells to which the player can actually move pieces at this moment
    king = None #The player's king
    checked = False     #Whether the player's king is attacked or not
    checking_pieces = None      #The player's pieces attacking the opponent's king
    my_turn = False     #Whether it's the player's turn now or not
    can_win = True      #Whether the player has enough material for checkmating the opponent or not

    #Initializing the player
    def __init__(self,color,board):
            #Assigning player's color and the board for the match
            self.color = color
            self.board = board
            #Defining back row and pawn row according to color
            back_row = 0 if color == Color.WHITE else 7
            pawn_row = 1 if color == Color.WHITE else 6
            #Defining set attributes as such
            self.pieces = []
            self.all_target_cells = []
            self.all_move_cells = []
            self.checking_pieces = []
            #Creating all 16 pieces in their original positions and adding them to the player's set of pieces
            #Creating the eight pawns
            p1 = Pawn(self,board.cells[pawn_row][0])
            self.pieces.append(p1)
            p2 = Pawn(self,board.cells[pawn_row][1])
            self.pieces.append(p2)
            p3 = Pawn(self,board.cells[pawn_row][2])
            self.pieces.append(p3)
            p4 = Pawn(self,board.cells[pawn_row][3])
            self.pieces.append(p4)
            p5 = Pawn(self,board.cells[pawn_row][4])
            self.pieces.append(p5)
            p6 = Pawn(self,board.cells[pawn_row][5])
            self.pieces.append(p6)
            p7 = Pawn(self,board.cells[pawn_row][6])
            self.pieces.append(p7)
            p8 = Pawn(self,board.cells[pawn_row][7])
            self.pieces.append(p8)
            #Creating the two knights
            kn1 = Knight(self,board.cells[back_row][1])
            self.pieces.append(kn1)
            kn2 = Knight(self,board.cells[back_row][6])
            self.pieces.append(kn2)
            #Creating the two bishops
            b1 = Bishop(self,board.cells[back_row][2])
            self.pieces.append(b1)
            b2 = Bishop(self,board.cells[back_row][5])
            self.pieces.append(b2)
            #Creating the two rooks
            r1 = Rook(self,board.cells[back_row][0])
            self.pieces.append(r1)
            r2 = Rook(self,board.cells[back_row][7])
            self.pieces.append(r2)
            #Creating the queen
            q = Queen(self,board.cells[back_row][3])
            self.pieces.append(q)
            #Creating the king
            k = King(self,board.cells[back_row][4])
            self.pieces.append(k)
            #Assigning the king piece
            self.king = k

    #Moving a piece as part of a player's turn    
    def move_piece(self,piece,next_cell):
            #If indeed the piece belongs to the layer and it can move to the specified cell...
            if piece in self.pieces and piece.color==self.color and next_cell in piece.move_cells:
            #if piece.current_cell.is_occupied and piece.current_cell.color==self.color:
                    #...moving the piece...
                    piece.move(next_cell)
                    #...and resetting the opponent's en-passant piece as the player just made a move
                    self.opponent.reset_en_passant_piece()

    #Removing a piece off the player's side               
    def remove_piece(self,piece):
            #If indeed the piece belongs to the player...
            if piece in self.pieces:
                    #...updating its cell as empty...
                    piece.current_cell.update()
                    #...and removing that piece from the player's inventory, then deleting its object
                    self.pieces.remove(piece)
                    del piece

    #Promoting a pawn reaching the opponent's edge to a higher-ranked piece    
    def promote_pawn(self,pawn,new_piece_type):
            new_piece = None        #The new piece
            cc = self.board.cells[pawn.current_cell.position[0]][pawn.current_cell.position[1]]     #The pawn's current cell
            #The player removes the pawn
            self.remove_piece(pawn)
            #A new piece is created at the same cell as the pawn
            if new_piece_type==Piece_type.QUEEN:
                    new_piece = Queen(self,cc)
            elif new_piece_type==Piece_type.ROOK:
                    new_piece = Rook(self,cc)
            elif new_piece_type==Piece_type.BISHOP:
                    new_piece = Bishop(self,cc)
            else:
                    new_piece = Knight(self,cc)
            #Since this is not the original position for such a piece, it is treated as if it had moved    
            new_piece.has_moved = True
            #Adding the piece to the player's inventory
            self.pieces.append(new_piece)

    #Setting the player's opponent   
    def set_opponent(self,player):
            self.opponent = player

    #Resetting the player's en-passant piece after an opponent's movement   
    def reset_en_passant_piece(self):
            #If there is an en-passant capturable pawn...
            if not self.en_passant_piece is None:
                    #...resetting this both for the piece itself and for the player
                    self.en_passant_piece.en_passant = False
                    print(self.en_passant_piece.current_cell.get_position(),self.en_passant_piece.en_passant)
                    self.en_passant_piece = None

    #Updating the player's pieces after any change on the board        
    def update_pieces(self):
            #Resetting all the targeting, moving and king-attacking info
            if self.all_target_cells is not None:
                    self.all_target_cells.clear()
            if self.all_move_cells is not None:
                    self.all_move_cells.clear()                
            if self.checking_pieces is not None:
                    self.checking_pieces.clear()

            knight_count=0  #number of knights the player has, needed for deciding whether the player can win or not
            bishop_count=0  #number of bishops the player has, needed for deciding whether the player can win or not
            #Going through the player's pieces...
            for p in self.pieces:
                    #...counting any knight or bishop
                    if p.piece_type==Piece_type.KNIGHT:
                            knight_count += 1
                    elif p.piece_type==Piece_type.BISHOP:
                            bishop_count += 1
                    #Updating the cells controled by the current piece
                    p.update_cells()
                    #Adding the piece's target cells to the player's set of target cells
                    target_cells = p.capture_cells if p.piece_type==Piece_type.PAWN else p.target_cells
                    for tc in target_cells:
            #               if (not p.piece_type==Piece_type.PAWN) or (p.piece_type==Piece_type.PAWN and abs(tc.position[1]-p.current_cell.position[1])==1):
                            self.all_target_cells.append(tc)
                    #If it's the player's turn now, adding the piece's actual move cells to the player's set of move cells
                    if self.my_turn:
                            for mc in p.move_cells:
                                    self.all_move_cells.append(mc)
            #Obtaining total number of pieces
            np = len(self.pieces)
            #If the player has (a) only king, (b) king+knight/bishop, (c) king+two knights, then the player cannot win and won't be able to win henceforth
            if np==1 or (np==2 and (knight_count or bishop_count)) or (np==3 and knight_count==2):
                    self.can_win = False

            
#Timer for routinely checking messages from a player client to match managing server
class Server_socket_timer(Timer):
    server = None   #Match managing server
    client = None   #The player client
    interval = 0.05     #Interval for checking messages

    #Initializing the timer
    def __init__ (self, server, client):
            self.server = server        #Assigning the match mananging server
            self.client = client        #Assigning the player client
            #Initializing the embedded timer with the match server method 'check_messages' to be invoked every interval 
            Timer.__init__(self, self.interval, self.server.check_messages)

    #The timer routine function
    def run(self):
            #A permanent loop invoking the server 'check_messages' method
            while (not self.finished.wait(self.interval)):
                    self.server.check_messages(self.client)
        

# A match managing server        
class Match:
    n_matches = 0       #Matches played by the two players so far
    board = None        #The virtual board
    white_player = None         #The virtual player on the white side
    black_player = None         #The virtual player on the black side
    game_started = False        #Whether or not the current game started
    status = Status.NEW_GAME    #Status of the game
    move_count = 0              #Moves made in the game so far
    passivity_count = 0         #Moves made since the last piece capture or pawn move
    is_white_turn = True        #Whether it's the white player's turn or not
    player_time = 0
    player = None               #The player that who has turn now
    move_annotation = None      #Annotation of last move
    position_log = None         #A log of all board position in the game so far
    timer = None                #Timer counting the time for the player whose turn is now
    time_left = None            #Time left for each of the players
    time_stamp = 0              #The universal time at a given point (needed for timer calculations)
    server_socket = None        #The communication socket of the match managing server
    clients = None              #The communication sockets of the player clients
    client_flags = None         #Indication for meta-communication between the players (new game, draw offer etc.)
    socket_timers = None        #Timers for checking messages from the player clients

    #Initializing the server
    def __init__(self,player_time,server_address):
            #Setting the time each side would have for a game
            self.player_time = player_time
            #Initializing the list objects containing the player clients, the socket timers for client messages and the meta-communication flags
            self.clients = []
            self.socket_timers = []
            self.client_flags = []
            #Creating all necessary virtual components for a new game, including board and players
            self.create()
            #Updating the status of the board, players and timers so a game can begin once player clients make contact
            self.update_status(Action.NONE)
            #Creating the server socket in order to receive communication from clients
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #Binding the socket to the address provided
            self.server_socket.bind(server_address)
            #Awaiting client communication
            self.server_socket.listen()
            client_socket = None
            #A loop running until two player clients have made contact so the game can start
            while len(self.clients) < 2:
                    #Accepting contact from a player client
                    client_socket, client_address = self.server_socket.accept()
                    #If contact was made...
                    if not client_socket is None:
                            #...adding the player client socket...
                            self.clients.append(client_socket)
                            #...defining serial ID for the player client (for further communications)
                            client_ID = len(self.clients)
                            #...creating an initialization message for the player client, including specification of the player's color
                            message = self.status_to_bytearray(Color(client_ID))
                            #...sending the message to the player client so it can set itself up
                            self.clients[client_ID-1].sendall(message)
            #Now that both player clients are ready, the first game is about to begin
            self.n_matches = 1
            #Creating timers for checking messages by the server for each of the player clients
            st1 = Server_socket_timer(self, self.clients[0])
            self.socket_timers.append(st1)
            st2 = Server_socket_timer(self, self.clients[1])
            self.socket_timers.append(st2)
            #Starting the message checking timers
            self.socket_timers[0].start()
            self.socket_timers[1].start()
                        
    #Setting up components before a match
    def create(self):
            #Creating the empty board
            self.board = Board()
            #Creating the virtual white player side
            self.white_player = Player(Color.WHITE,self.board)
            #Creating the virtual black player side
            self.black_player = Player(Color.BLACK,self.board)
            #Setting the two players as each other's opponents
            self.white_player.set_opponent(self.black_player)
            self.black_player.set_opponent(self.white_player)
            #Setting the status indicating that a new game is about to begin
            self.status = Status.NEW_GAME
            #Ensuring the white begins
            self.is_white_turn = True
            self.player = self.white_player
            self.player.my_turn = True
            #Updating the white player's possible moves given that it's its turn 
            self.player.update_pieces()
            #Creating an empty board position log list
            self.position_log = []
            #Reseting passivity count and move count to 0
            self.passivity_count = 0
            self.move_count = 0
            #Setting up time counters for the coming game
            self.time_left = [self.player_time,self.player_time]
            #Ensuring that the coming game isn't on yet
            self.game_started = False
            #Resetting the annotation of the last move
            self.move_annotation = None
            #Resetting the player clients meta-communication flags so none of them is currently communicating
            self.client_flags = [False, False]
            #Printing the board for monitoring
            self.board.print_board()

    #Deleting components before new ones are created for a new match
    def destroy(self):
            del self.board
            del self.white_player
            del self.black_player
            del self.position_log

    #Resetting everything for a new (2nd or later) match
    def new_match(self):
            #Deleting components
            self.destroy()
            #Updating the number of matches
            self.n_matches +=1
            #Recreating components
            self.create()
            #Determining colors (swithcing sides)
            if self.n_matches % 2:
                    clr1 = Color.WHITE
                    clr2 = Color.BLACK
            else:
                    clr1 = Color.BLACK
                    clr2 = Color.WHITE

            #Sending reset messages to the two player clients with the colors switched
            message = self.status_to_bytearray(clr1)
            self.clients[0].sendall(message)
            message = self.status_to_bytearray(clr2)
            self.clients[1].sendall(message)
            #Updating the status
            self.update_status(Action.NONE)

    #Checking new messages from a given player client
    def check_messages(self, client):
            #Trying to obtain a message from the client on the client socket queue
            data = client.recv(128)
            #If a message arrived...
            if not data is None:
                    #print(data)
                    #...processing the message
                    self.take_data(data)
                
    #Updating the current status of the match as well as other components and informing the clients
    def update_status(self, action, time_left=None, from_cell=None, to_cell=None, promotion=None):
            #If this is the preparation stage for a new game...
            if self.status == Status.NEW_GAME:
                    if self.client_flags[0] and self.client_flags[1]:
                            self.client_flags = [False,False]
                            self.status = Status.GAME_ON                            
                            #... registering the time for timer calculation
                            self.time_stamp = time.time()
                    else:
                            return
            if self.status == Status.DRAW_OFFERED:
                    if action == Action.OFFER:
                            self.client_flags = [False,False]
                            self.status = Status.DRAW_AGREED
                    else:
                            self.client_flags = [False,False]
                            self.status = Status.GAME_ON
            if self.status == Status.GAME_ON:
                    if not self.game_started:
                            self.game_started = True
                            self.move_count = 1
                    else:
                            if action == Action.OFFER:
                                    self.status = Status.DRAW_OFFERED
                            elif action == Action.RESIGN:
                                    self.status = Status.RESIGNED if time_left else Status.TIME_UP
                            elif action == Action.PLAY:
                                    if self.is_white_turn:
                                            self.time_left[0] = time_left
                                    else:
                                            self.time_left[1] = time_left

                                    if from_cell.is_occupied and (from_cell.color==Color.WHITE)==self.is_white_turn:
                                            piece = from_cell.piece
                                            captured = to_cell.is_occupied
                                            self.player.move_piece(piece, to_cell)
                                            if piece.piece_type==Piece_type.PAWN and (to_cell.position[0]==0 or to_cell.position[0]==7) and not promotion is None:
                                                    self.player.promote_pawn(piece, promotion)
                                            self.annotate_move(piece, from_cell, to_cell, captured, promotion)
                                            key_count = self.update_position_log()
                                            if key_count > 1:
                                                    self.status = Status.REPEATED_MOVES
                                            self.player.my_turn = False
                                            self.player.update_pieces()
                                            #Switching turns
                                            self.is_white_turn = not self.is_white_turn
                                            self.player = self.white_player if self.is_white_turn else self.black_player
                                            self.player.my_turn = True
                                            #If it's the white player's turn increasing the move count
                                            if self.is_white_turn:
                                                    self.move_count += 1
                                            #Updating the player's movement possibilities
                                            self.player.update_pieces()
                                            if (not self.player.can_win) and (not self.player.opponent.can_win):
                                                    self.status = Status.NO_MATERIAL

                                            if not self.player.all_move_cells:
                                                    #...updating status to checkmate or stalemate depending on whether or not the player's king is attacked
                                                    self.status = Status.CHECKMATE if self.player.checked else Status.STALEMATE
                                            else:
                                                    self.passivity_count = 0 if ((piece.piece_type==Piece_type.PAWN) or to_cell.is_occupied) else self.passivity_count+1
                                                    if self.passivity_count==100:
                                                            self.status = Status.PASSIVITY
            if self.status in [Status.DRAW_AGREED,Status.REPEATED_MOVES,Status.NO_MATERIAL, Status.PASSIVITY,Status.TIME_UP,Status.RESIGNED,Status.CHECKMATE,Status.STALEMATE]:
                    if self.client_flags[0] and self.client_flags[1]:
                            self.client_flags = [False,False]
                            self.new_match()
                            return
                    
            sba = self.status_to_bytearray()
                    #print(sba)
                    #If indeed there are two player clients, sending the status representation to them and resetting the annotation string before the next move
            if len(self.clients)==2:
                    self.clients[0].sendall(sba)
                    self.clients[1].sendall(sba)
                    self.move_annotation = None

                                     
                            
                                    
                            
                            
            #If not at preparation stage...
#            else:
                    #If the game is on or just about to begin...
 #                   if self.status == Status.GAME_ON:
                            #...registering a snapshot of the current board situation
#                            self.update_position_log()
                            #If the game really started, then we're here after the current player's move, so...
#                            if self.game_started:
                                    #...it's no longer that player's turn
#                                    self.player.my_turn = False
                                    #...hence updating its targets and (no-)movement possibilities
#                                    self.player.update_pieces()
                                    #Switching turns
#                                    self.is_white_turn = not self.is_white_turn
#                                    self.player = self.white_player if self.is_white_turn else self.black_player
#                                    self.player.my_turn = True
                                    #If it's the white player's turn increasing the move count
#                                    if self.is_white_turn:
#                                            self.move_count += 1
                                    #Updating the player's movement possibilities
#                                    self.player.update_pieces()
                                    #If the status hasn't been changed (due to repeated moves) and the player can't move
#                                    if self.status == Status.GAME_ON and not self.player.all_move_cells:
                                            #...updating status to checkmate or stalemate depending on whether or not the player's king is attacked
#                                            self.status = Status.CHECKMATE if self.player.checked else Status.STALEMATE
                                            #...printing the status for monitoring purposes
#                                            print(self.status)
                            #If the game is starting now...
#                            else:
#                                    print("Game starting now!")
                                    #...updating the current player's movement possibilities
#                                    self.player.update_pieces()
                                    #...Setting the indication that the game is on and updating move count for the first move
#                                    self.game_started = True
#                                    self.move_count = 1
                    #Obtaining representation of the overall status for sending to the player clients
#                    sba = self.status_to_bytearray()
                    #print(sba)
                    #If indeed there are two player clients, sending the status representation to them and resetting the annotation string before the next move
#                    if len(self.clients)==2:
#                            self.clients[0].sendall(sba)
#                            self.clients[1].sendall(sba)
#                            self.move_annotation = None

    #Updating the board position log and cheking for repeated positions
    def update_position_log(self):
            #Obtaining key for current position
            key = self.board.position_to_int()

            #self.parse_position_log(key)

            key_count = 0 #Count of repetitions of current position
            #Iterating through previous positions
            for k in reversed(self.position_log):
                    #if the same key has occurred before, increasing its repetition count
                    if k==key:
                            key_count += 1
                            
            self.position_log.append(key)

            return key_count
        
            #If there were two repetitions (3 instances) of the same position, the status is changed to 'repeated moves' for draw
#            if key_count > 1:
#                    self.status = Status.REPEATED_MOVES
            #Otherwise, adding the key to the log
#            else:
#                    self.position_log.append(key)

    #def parse_position_log(self, position_log):
    #    cells = [[[Piece_type.NONE,Color.NONE] for c in range(8)] for r in range(8)]
    #    temp_log = position_log
    #    for i in range(64):
    #        l,p = divmod(temp_log,13)
    #        temp_log = l
    #        r,c = divmod(i,8)
    #        if p:
    #            pt = Piece_type(1+(p-1)%6)
    #            clr = Color(1+(p-1)//6)
    #        else:
    #            pt = Piece_type.NONE
    #            clr = Color.NONE
    #        cells[r][c]=[pt,clr]
    #    for r in reversed(cells):
    #        for c in r:
    #            if not c[0]==Piece_type.NONE:
    #                print(chr(9811+6*(c[1].value-1)+c[0].value),end='')
    #            else:
    #                print(chr(8195),end='')
    #        print()


    #Converting the entire game position to a server message to the client
    def status_to_bytearray(self,clr=Color.NONE):
            status_bytearray = bytearray()      #The bytearray to be sent to the client
            #First byte: status
            status_byte = self.status.value.to_bytes(1,'big')
            #Player identity information, to be conveyed eventually in the second byte, as follows:
            #If the current player ran out of time...
            if self.status==Status.TIME_UP:
                    #The current player is identified
                    player = self.white_player if self.is_white_turn else self.black_player
                    #If the opponent has enough material to win, its identity as the winner is represented by the opposite boolean value of the turn variable.
                    #Otherwise, the identity, as if indicating the current player, in fact indicates draw
                    player_identity = not self.is_white_turn if player.opponent.can_win else self.is_white_turn
            #Otherwise, i.e. if the current player still has time...
            else:
                    #...identity represents whose turn it is, except when color was given, in which case identity represents the intended color of the recipient client (for a new game)
                    player_identity = self.is_white_turn if clr==Color.NONE else clr==Color.WHITE
                    
            #Second byte: Identity        
            turn_byte = int(player_identity).to_bytes(1,'big')

            #Third and fourth bite: time left for the current player, in whole deci-seconds                        
            time_left = self.time_left[0] if self.is_white_turn else self.time_left[1]
            time_left_byte = int(time_left*10).to_bytes(2,'big')
            #Fifth to 34th byte: board snapshot
            position_byte_array = self.board.position_to_int().to_bytes(30,'big')
            #Adding all 34 bytes to the bytearray to be sent
            status_bytearray += status_byte
            status_bytearray += turn_byte
            status_bytearray += time_left_byte
            status_bytearray += position_byte_array
            #Now adding (potentially redundant) information about possible moves on the board in the coming turn, as follows:
            #Running through all the cells...
            for r in self.board.cells:
                    for c in r:
                            #...if the current cell is occupied...
                            if c.is_occupied:
                                    cell_position_byte = (c.position[0]*num_cols+c.position[1]).to_bytes(1,'big')       #A byte representing cell position on the board
                                    #...and only if this cell's piece can move...
                                    if c.piece.move_cells:
                                            #...first adding the cell position byte...
                                            status_bytearray += cell_position_byte
                                            moves_bytes = bytearray()   #A bytearray object representing the possible landing cells
                                            #... then running through all possible landing cells...
                                            for mc in c.piece.move_cells:
                                                    #... and representing each of them as a byte added to the landing cells bytearray
                                                    move_cell_byte = (mc.position[0]*num_cols+mc.position[1]).to_bytes(1,'big')
                                                    moves_bytes += move_cell_byte
                                            #...the second byte is the number of possible moves, essentially indicating the number of the following bytes to be treated as landing cells
                                            n_moves_byte = len(moves_bytes).to_bytes(1,'big')
                                            status_bytearray += n_moves_byte
                                            #...and then adding all the landing cells bytes to the bytearray 
                                            status_bytearray += moves_bytes
            #Finally, the string annotating the last move, if not already sent, is added, as follows:
            if not self.move_annotation is None:
                    #First, a byte indicating that there's annotation string coming
                    status_bytearray += annotation_byte_value
                    #Then, the string is converted to bytes
                    annotation_bytes = self.move_annotation.encode()
                    #Then, the number of the bytes is measured and added
                    status_bytearray += len(annotation_bytes).to_bytes(1,'big')
                    #Only then the bytes representing the annotation are added 
                    status_bytearray += annotation_bytes
            #At the very end of the bytearray to be sent, a final delimiter is added
            status_bytearray += last_byte_value

            #The bytearray is returned                                                   
            return status_bytearray
        
            
                    
    def take_data(self, data):
            client_data = bytearray(data)
            client_ID = int.from_bytes(client_data[0:1],'big')
            action = Action(int.from_bytes(client_data[1:2],'big'))
            time_left = int.from_bytes(client_data[2:4],'big')/10
            if action==Action.PLAY:
                    self.client_flags = [False,False]
                    from_cell_int = int.from_bytes(client_data[4:5],'big')
                    to_cell_int = int.from_bytes(client_data[5:6],'big')
                    fr,fc = divmod(from_cell_int, num_cols)
                    tr,tc = divmod(to_cell_int, num_cols)
                    from_cell = self.board.cells[fr][fc]
                    to_cell = self.board.cells[tr][tc]
                    
                    tmp = int.from_bytes(client_data[6:7], 'big')
                    if not tmp==int.from_bytes(last_byte_value,'big'):
                            promotion = Piece_type(tmp)
                    else:
                            promotion = None
                    self.update_status(action, time_left, from_cell, to_cell, promotion)

            elif action==Action.RESIGN:
                    self.client_flags = [False,False]
                    self.update_status(action, time_left)
                            
            elif action==Action.OFFER:
                    self.client_flags[client_ID-1] = True
                    self.update_status(action)

                    


                    
                    
#            if action==Action.PLAY:
#                    if self.status==Status.DRAW_OFFERED:
#                            self.status = Status.GAME_ON
#                            
#                    if self.is_white_turn:
#                            self.time_left[0] = time_left
#                    else:
#                            self.time_left[1] = time_left
#
#                    if from_cell.is_occupied and (from_cell.color==Color.WHITE)==self.is_white_turn:
#                            piece = from_cell.piece
#                            to_cell = self.board.cells[tr][tc]
#                            self.passivity_count = 0 if ((piece.piece_type==Piece_type.PAWN) or to_cell.is_occupied) else self.passivity_count+1
#                            if self.passivity_count==100:
#                                    self.status = Status.PASSIVITY
#                            self.annotate_move(piece, to_cell) 
#                            player = self.white_player if self.is_white_turn else self.black_player
#                            player.move_piece(piece, to_cell)
#                            if piece.piece_type==Piece_type.PAWN and (tr==0 or tr==7) and not promotion is None:
#                                    player.promote_pawn(piece, promotion)
#                            self.update_status()
#
#           elif action==Action.RESIGN:
#                    if not time_left:
#                            self.status = Status.TIME_UP
#                            self.update_status()
#                    else:
#                            self.status = Status.RESIGNED
#                            print("resigned")
#                            self.update_status()
#
#                            
#            elif action==Action.OFFER:
#                    if self.client_flags[0] and self.client_flags[1]:
#                            self.client_flags = [False,False]
#                            if self.status==Status.DRAW_OFFERED:
#                                    self.status = Status.DRAW_AGREED
#                                    self.client_flags = [False,False]
#                                    print("draw")
#                                    self.update_status()
#                            elif self.status==Status.NEW_GAME:
#                                    self.status = Status.GAME_ON
#                                    self.update_status()
#                            else:
#                                    print("both clients sent new match")
#                                    self.new_match()
#                    elif self.status==Status.GAME_ON:
#                            self.status = Status.DRAW_OFFERED
#                            print("draw offered")
#                            self.update_status()
                            
            #else:
            #        self.update_status()
                    
                            
            

    #$def time_ran_out(self):
    #$    if self.player.opponent.can_win:
    #$            self.status = Status.TIME_UP
    #$            self.update_status()
            
    def annotate_move(self, piece, cc, nc, captured, promotion=None):
        cca = cc.get_position()
        nca = nc.get_position()
        pa = ""
        prefix = str(self.move_count)+". " if self.is_white_turn else ""
        castling = False
        if piece.piece_type==Piece_type.KING:
                if nc.position[1]==cc.position[1]+2:
                        self.move_annotation = prefix + "0-0 "
        #$                    self.annotation_box.insert(tkinter.END,annotation)
                        return
                elif nc.position[1]==cc.position[1]-2:
                        self.move_annotation = prefix + "0-0-0 "
        #$                    self.annotation_box.insert(tkinter.END,annotation)
                        return
                else:
                        pa = "K"                    
        elif piece.piece_type==Piece_type.QUEEN:
                pa = "Q"
        elif piece.piece_type==Piece_type.ROOK:
                pa = "R"
        elif piece.piece_type==Piece_type.BISHOP:
                pa = "B"
        elif piece.piece_type==Piece_type.KNIGHT:
                pa = "N"
        else:
                if not cc.position[1]==nc.position[1]:
                        pa = cc.get_position()[0]
        
        for p in self.player.pieces:
                if p.piece_type==piece.piece_type and not p.piece_type==Piece_type.PAWN and not p.current_cell.position==cc.position and nc in p.target_cells:
                        pa += cca
                        break
        
        if captured or (piece.piece_type==Piece_type.PAWN and not cc.position[1]==nc.position[1]):
                pa += "x"

        if not promotion is None:
                if promotion==Piece_type.QUEEN:
                        prom = ":Q"
                elif promotion==Piece_type.ROOK:
                        prom = ":R"
                elif promotion==Piece_type.BISHOP:
                        prom = ":B"
                else:
                        prom = ":N"
        else:
                prom = ""

        self.move_annotation = prefix + pa + nca + prom + " "
        
        #$        self.annotation_box.insert(tkinter.END,annotation)
               

class Chess_timer(Timer):
        client_match = None
        timer_id = 0
        def __init__(self, client_match):
                self.client_match = client_match
                time_left = self.client_match.player_time_left if self.client_match.player_turn else self.client_match.opponent_time_left
                interval = 0.1 if self.client_match.player_time_left<20 else 1.0
                self.timer_id = int(1000*random.random())
                Timer.__init__(self, interval, self.client_match.tick)
        def run(self):
                time_left = self.client_match.player_time_left if self.client_match.player_turn else self.client_match.opponent_time_left
                while (not self.finished.wait(self.interval) and time_left>0):
                        self.client_match.time_stamp = time.time()
                        rounding_digits = 1 if time_left<=20 else 0
                        time_left = round(time_left - self.interval, rounding_digits)
                        if self.client_match.player_turn:
                                tmp = "player time left "
                                self.client_match.player_time_left = time_left
                        else:
                                tmp = "opponent time left "
                                self.client_match.opponent_time_left = time_left
                        if time_left<=20:
                                self.interval=0.1
                        #print("client ", self.client_match.client_ID, ": ", tmp, time_left)
                        self.client_match.tick(self.timer_id)
                if self.client_match.player_turn and not time_left:
                        self.client_match.time_ran_out()
        def cancel(self, player_turn):
                ts = self.client_match.time_stamp
                self.client_match.time_stamp = time.time()
                time_elapsed = self.client_match.time_stamp - ts
                rounding_digits = 1 if self.interval==0.1 else 0
                if player_turn:
                        self.client_match.player_time_left = round(self.client_match.player_time_left - time_elapsed, rounding_digits)
                        if self.client_match.player_time_left < 0:
                                self.client_match.player_time_left = 0                                
                else:
                        self.client_match.opponent_time_left = round(self.client_match.opponent_time_left - time_elapsed, rounding_digits)
                print ("stopping timer", self.timer_id, " at", self.client_match.player_time_left if player_turn else self.client_match.opponent_time_left)
                Timer.cancel(self)
                
class Client_cell:
        piece_type = Piece_type.NONE
        color = Color.NONE
        position = [0,0]
        target_cells = []
        is_white_cell = False
        def __init__(self,row,column):
                self.position = [row,column]
                self.is_white_cell = True if ((row%2)+column)%2 else False
                #print("created cell ", row, column, self.position)


class Client_socket_timer(Timer):
        client_match = None
        interval = 0.1
        def __init__ (self, client_match):
                self.client_match = client_match
                Timer.__init__(self, self.interval, self.client_match.check_messages)
        def run(self):
                while (not self.finished.wait(self.interval)):
                        self.client_match.check_messages()
                        


class Client_match:
        n_matches = 0
        client_ID = 0
        status = Status.NEW_GAME
        player_color = Color.NONE
        action = Action.NONE
        player_turn = False
        player_time_left = 0
        opponent_time_left = 0
        from_cell = None
        to_cell = None
        time_stamp = 0
        cells = [[]]
        client_socket = None
        client_GUI = None
        timer = None
        game_started = False
        socket_timer = None
        last_move_annotation = None
        def __init__(self, sa):
                self.cells = [[Client_cell(r,c) for c in range(num_cols)] for r in range(num_rows)]
                self.client_GUI = Client_GUI(self)
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect(sa)
                #message = "hello"
                #self.client_socket.sendall(message.encode('utf-8'))
                data = self.client_socket.recv(128)
                if not data is None:
                        self.update_status(data)
                        self.socket_timer = Client_socket_timer(self)
                if not self.socket_timer is None:
                        self.socket_timer.start()
                #self.client_ID = client_ID
                #self.player_color = color
                #for r in self.cells:
                #        for c in r:
                #                print("created cell ", c.position)
        
        def check_messages(self):
                data = self.client_socket.recv(128)
                if not data is None:
                        self.update_status(data)


        def update_status(self, data):
            status_data = bytearray(data)
            print(status_data)
            is_white_turn = bool(status_data[1])
            #print(is_white_turn)
            cs = self.status
            self.status = Status(int.from_bytes(status_data[0:1],'big'))
            print(self.status)
            #print(self.status)
            if not self.status==Status.DRAW_OFFERED:
                pt = self.player_turn
                time_left_data = (int.from_bytes(status_data[2:4],'big'))/10
                if (self.player_color==Color.BLACK)==is_white_turn:
                        otl = self.opponent_time_left
                        self.opponent_time_left = time_left_data
                position_data = int.from_bytes(status_data[4:34],'big')
                for r in range(num_rows):
                        for c in range(num_cols):
                                self.cells[r][c].piece_type = Piece_type.NONE
                                self.cells[r][c].color = Color.NONE
                                self.cells[r][c].target_cells.clear()
                self.parse_position_data(position_data)
                if self.status == Status.NEW_GAME:
                        if self.client_ID==0:
                                self.client_ID = 1 if is_white_turn else 2
                        self.n_matches += 1
                        self.player_time_left = time_left_data
                        self.opponent_time_left = time_left_data
                        if is_white_turn:
                                self.player_color = Color.WHITE
                                self.player_turn = True
                        else:
                                self.player_color = Color.BLACK
                                self.player_turn = False
                        if self.n_matches<=1:
                                self.client_GUI.new_match(self.player_color)
                                print(self.client_ID,self.player_color,self.n_matches)
                                self.client_GUI.window.after(100, self.client_GUI.window.mainloop)
                        else:
                                self.client_GUI.new_match()
                        self.send_data(Action.OFFER)
                        return
                        #self.client_GUI.window.mainloop()
                elif self.status == Status.GAME_ON:
                        if not self.timer is None and self.timer.is_alive():
                                self.timer.cancel(False)
                        if self.action == Action.OFFER:
                                self.action = Action.NONE
                        #print("hi there")
                        self.player_turn = (self.player_color==Color.WHITE)==is_white_turn
                        self.time_stamp = time.time()
                        i=34
                        if self.player_turn:                                
                                while not ((status_data[i]==int.from_bytes(last_byte_value,'big')) or (status_data[i]==int.from_bytes(annotation_byte_value,'big'))):
                                    position_int = int.from_bytes(status_data[i:i+1],'big')
                                    r,c = divmod(position_int,num_cols)
                                    #print(position_int, r, c)
                                    is_OK = True if self.cells[r][c].color==self.player_color else False                                        
                                    n_moves = int.from_bytes(status_data[i+1:i+2],'big')
                                    target_cells = []
                                    for j in range(i+2,i+2+n_moves):
                                            row,column = divmod(int.from_bytes(status_data[j:j+1],'big'),num_cols)
                                            target_cell = [row,column]
                                            if is_OK:
                                                    target_cells.append(target_cell)
                                    self.cells[r][c].target_cells = target_cells
                                    print(self.cells[r][c].target_cells)
                                    i = i+2+n_moves
                        else:
                                while not ((status_data[i]==int.from_bytes(last_byte_value,'big')) or (status_data[i]==int.from_bytes(annotation_byte_value,'big'))):
                                    i += 1
                        if status_data[i]==int.from_bytes(annotation_byte_value,'big'):
                                self.last_move_annotation = status_data[i+2:i+2+int.from_bytes(status_data[i+1:i+2],'big')].decode()
                        print("starting timer", is_white_turn)
                        if not self.game_started:
                                #print("starting")
                                #self.client_GUI.update_status()
                                self.game_started = True
                                #self.client_GUI.window.after(100, self.client_GUI.window.mainloop)
                                #return
                        #else:
                        self.timer = Chess_timer(self)
                        self.timer.start()
                                
                else:
                        if not self.timer is None:
                                self.timer.cancel(self.player_turn)
                        if self.status == Status.TIME_UP:
                                self.player_turn = (self.player_color==Color.WHITE)==is_white_turn
                                #text = "white turn and " if ((self.player_color==Color.WHITE and pt) or (self.player_color==Color.BLACK and not pt)) else "black turn and "
                                #more_text = "opponent cannot win" if pt==is_white_turn else "opponent can win"
                                #print (text+more_text, self.client_ID, self.player_time_left)
                        elif self.status in [Status.CHECKMATE,Status.STALEMATE,Status.PASSIVITY,Status.REPEATED_MOVES,Status.NO_MATERIAL]:
                                i = 34
                                while not ((status_data[i]==int.from_bytes(last_byte_value,'big')) or (status_data[i]==int.from_bytes(annotation_byte_value,'big'))):
                                        i =+1
                                if status_data[i]==int.from_bytes(annotation_byte_value,'big'):
                                        self.last_move_annotation = status_data[i+2:i+2+int.from_bytes(status_data[i+1:i+2],'big')].decode()                                
                        
            if not self.client_GUI is None:
                    self.client_GUI.update_status()
                    self.last_move_annotation = None
                
        def send_data(self, action, from_cell=None, to_cell=None, promotion=None):
                data_bytearray = bytearray()
                id_byte = self.client_ID.to_bytes(1,'big')
                data_bytearray += id_byte
                self.action = action
                action_byte = action.value.to_bytes(1,'big')
                data_bytearray += action_byte
                if action==Action.PLAY:
                        self.timer.cancel(True)
                        time_left_bytes = int(self.player_time_left*10).to_bytes(2,'big')
                        data_bytearray += time_left_bytes
                        if not from_cell is None and not to_cell is None:
                                from_cell_byte = (from_cell[0]*num_cols+from_cell[1]).to_bytes(1,'big')
                                data_bytearray += from_cell_byte
                                to_cell_byte = (to_cell[0]*num_cols+to_cell[1]).to_bytes(1,'big')
                                data_bytearray += to_cell_byte
                                if self.cells[from_cell[0]][from_cell[1]].piece_type==Piece_type.PAWN and (to_cell[0]==0 or to_cell[0]==7) and not promotion is None:
                                        promotion_byte = promotion.value.to_bytes(1,'big')
                                        data_bytearray += promotion_byte
                elif action==Action.RESIGN:
                        self.timer.cancel(self.player_turn)
                        time_left_bytes = int(self.player_time_left*10).to_bytes(2,'big')
                        print(self.client_ID, self.player_color, self.n_matches, self.status, self.player_turn, self.player_time_left)
                        print("resigning")
                        data_bytearray += time_left_bytes
                data_bytearray += last_byte_value
                print(data_bytearray)
                self.client_socket.sendall(data_bytearray)
                                
                        
        def move(self, from_cell, to_cell, promotion=None):
                if not promotion is None:
                        self.send_data(Action.PLAY, from_cell, to_cell, promotion)
                else:
                        self.send_data(Action.PLAY, from_cell, to_cell)
                
        def parse_position_data(self, position_data):
                temp = position_data
                for i in range(64):
                    l,p = divmod(temp,13)
                    temp = l
                    r,c = divmod(i,8)
                    if p:
                        pt = Piece_type(1+(p-1)%6)
                        clr = Color(1+(p-1)//6)
                    else:
                        pt = Piece_type.NONE
                        clr = Color.NONE
                    self.cells[r][c].piece_type = pt
                    self.cells[r][c].color = clr
                    #print(r,c,pt,clr)
                
        def tick(self, timer_id):
                time_left = self.player_time_left if self.player_turn else self.opponent_time_left
                print(timer_id, "tick", time_left)
                self.client_GUI.update_timer(time_left)
        
                                
        def time_ran_out(self):
                self.player_time_left = 0
                self.send_data(Action.RESIGN)

        def new_match(self):
                self.game_started = False
                print("new match")
                self.send_data(Action.OFFER)

        def is_cell_in_target_cells(self,cell1,cell2):
                found = False
                #position1 = cell1
                if not cell2.target_cells is None:
                        for tc in cell2.target_cells:
                                if cell1[0]==tc[0] and cell1[1]==tc[1]:
                                        found = True
                                        break
                else:
                        return False
                return found

        def resign(self):
                print(self.client_ID, self.player_color, self.n_matches, self.status, self.player_turn, self.player_time_left) 
                if self.status==Status.GAME_ON or self.status==Status.DRAW_OFFERED:
                        self.send_data(Action.RESIGN)
        
        def offer_draw(self):
                if self.status==Status.GAME_ON or self.status==Status.DRAW_OFFERED:                
                        self.send_data(Action.OFFER)
                                        
class Cell_button:
        match_GUI = None
        frame = None
        button = None
        cell = None
        clicked = False
        cell_color = None
        available_color = None
        target_color = None
        clicked_color = None
        last_occupied = False
        last_color = Color.NONE
        last_piece_type = Piece_type.NONE
        def __init__ (self,match_GUI,cell):
                self.match_GUI = match_GUI
                self.cell = cell
                #print("created button for cell ", self.cell.position)
                self.cell_color = "white" if cell.is_white_cell else "#afa"
                self.available_color = "#ddd" if cell.is_white_cell else "#8d8"
                self.target_color = "#bbb" if cell.is_white_cell else "#6b6"
                self.clicked_color = "#888" if cell.is_white_cell else "#383"
                self.frame = tkinter.Frame(self.match_GUI.window,width=30,height=30,bg=self.cell_color)
                #self.frame.grid(column=cell.position[1]+2, row=num_rows-cell.position[0]+2)
                self.button = tkinter.Button(self.frame,bg=self.cell_color,activebackground=self.cell_color,relief="flat",justify="center",\
                                             font=("Lucida Console",20),command=self.button_click)
                self.button.place(relx=0.02,rely=0.02,relheight=0.96,relwidth=0.96)
        def update(self,new_match=False):
                if new_match or not (self.last_color==self.cell.color and self.last_piece_type==self.cell.piece_type):
                        self.last_color = self.cell.color
                        self.last_piece_type = self.cell.piece_type
                        if not self.last_piece_type==Piece_type.NONE:
                                foreground = "gray" if self.last_color==Color.WHITE else "black"
                                self.button.configure(fg=foreground,disabledforeground=foreground,text=piece2symbol(self.last_piece_type,self.last_color))
                        else:
                                self.button.configure(text='')
        def button_click(self):
                if not self.match_GUI.promotion_dialog_on:
                        print(self.cell.position)
                        if (not self.match_GUI.clicked_button) or \
                        ((not self.cell.piece_type==Piece_type.NONE) and (self.cell.color==self.match_GUI.client_match.player_color)):
                                self.match_GUI.clicked_button = self
                                self.match_GUI.update_buttons()
                        else:
                                self.match_GUI.move(self.match_GUI.clicked_button.cell,self.cell)
                        

                
class Client_GUI:
        #$match = None
        #$board = None
        client_match = None #$
        window = None
        head_label = None
        bottom_timer_label = None
        top_timer_label = None
        annotation_frame = None
        annotation_box = None
        new_match_button = None
        cell_buttons = None
        row_labels = None
        column_labels = None
        clicked_button = None
        n_matches = 0
        promotion_dialog_on = False

        #$def __init__(self,match):
        def __init__(self,client_match): #$
                cell_buttons = []
                row_labels = []
                column_labels = []
                #$self.match = match
                self.client_match = client_match #$
                #$self.board = match.board
                self.window = tkinter.Toplevel()
                geometry_str = '500x500+' + str(50+int(800*random.random())) + '+100'
                self.window.geometry(geometry_str)
                self.head_label = tkinter.Label(self.window,text="White Turn",justify="center",font=("Lucida Console",14))
                self.head_label.grid(row=0,column=0,columnspan=12)
                frame1 = tkinter.Frame(self.window,width=50,height=30)
                frame1.grid(row=1,column=0)
                #$m,s = divmod(int(self.match.time_left[0]),60)
                m,s = divmod(self.client_match.player_time_left,60) #$
                time_string = f'{m:02d}:{s:02d}'
                self.top_timer_label = tkinter.Label(frame1,text=time_string,justify="right",font=("Lucida Console",11))
                self.top_timer_label.place(relheight=1.0,relwidth=1.0)
                frame2 = tkinter.Frame(self.window,width=50,height=30)
                frame2.grid(row=12,column=0)
                self.bottom_timer_label = tkinter.Label(frame2,text=time_string,justify="right",font=("Lucida Console",11))
                self.bottom_timer_label.place(relheight=1.0,relwidth=1.0)
                self.annotation_frame = tkinter.Frame(self.window,width=180,height=300)
                self.annotation_frame.grid(row=2,column=12,rowspan=10,columnspan=6)
                self.annotation_box = scrolledtext.ScrolledText(self.annotation_frame,bg="white",font=("Lucida Console",8))
                self.annotation_box.place(relheight=1.0,relwidth=1.0)
                #$self.new_match_button = tkinter.Button(self.window, text="New Match?", justify="center",font=("Lucida Console",14),command=self.match.new_match)
                self.resign_button = tkinter.Button(self.window, text="Resign?", justify="center",font=("Lucida Console",10),command=self.client_match.resign)
                self.resign_button.grid(row=12,column=2,columnspan=3)
                self.draw_button = tkinter.Button(self.window, text="Draw?", justify="center",font=("Lucida Console",10),command=self.client_match.offer_draw)
                self.draw_button.grid(row=12,column=5,columnspan=5)
                self.new_match_button = tkinter.Button(self.window, text="New Match?", justify="center",font=("Lucida Console",14),command=self.client_match.new_match) #$
                self.new_match_button.pack_forget()
                for i in range(16):
                        rl = tkinter.Label(self.window, text = str(i%8+1), justify="center",font=("Lucida Console",14))
                        row_labels.append(rl)
                        #print("creating row label", len(row_labels))
                        cl = tkinter.Label(self.window, text = chr(65345+i%8), justify="center",font=("Lucida Console",14))
                        column_labels.append(cl)
                        #print("creating column label", len(column_labels))
                self.row_labels = row_labels
                self.column_labels = column_labels
                self.display_labels()
                #for r in range(3,11):
                        
                #        label1 = tkinter.Label(self.window, text=str(11-r),justify="center",font=("Lucida Console",14))
                #        label2 = tkinter.Label(self.window, text=str(11-r),justify="center",font=("Lucida Console",14))
                #        label1.grid(row=r,column=1)
                #        label2.grid(row=r,column=10)
                #for c in range(2,10):
                #        label1 = tkinter.Label(self.window, text=chr(65343+c),justify="center",font=("Lucida Console",14))
                #        label2 = tkinter.Label(self.window, text=chr(65343+c),justify="center",font=("Lucida Console",14))
                #        label1.grid(row=2,column=c)
                #        label2.grid(row=11,column=c)

                #$for r in self.board.cells:
                for r in self.client_match.cells: #$
                        for c in r:
                                #print ("creating button for ", c.position)
                                cb = Cell_button(self,c)
                                cell_buttons.append(cb)
                self.cell_buttons = cell_buttons
                self.display_buttons()
                self.update_buttons(True)
                self.window.lift()

        def display_labels(self):
                if self.client_match.player_color==Color.BLACK:
                        first_row = 3
                        first_column = 9
                        step = -1
                else:
                        first_row = 10
                        first_column = 2
                        step = 1

                for i in range(len(self.row_labels)):
                        self.row_labels[i].grid(row=first_row-step*(i%8),column=1+9*(i//8))
                        #print("row_label ", i, " for client ", self.client_match.client_ID, " in row ", first_row-step*(i%8), " column ", 1+9*(i//8))
                        self.column_labels[i].grid(row=2+9*(i//8),column=first_column+step*(i%8))
                        #print("column_label ", i, " for client ", self.client_match.client_ID, " in row ", 2+9*(i//8), " column ", first_column+step*(i%8))
                #for i in range(len(self.row_labels)):
                #        self.row_labels[i].grid(row=10-i%8,column=1+9*(i//8))
                #        self.column_labels[i].grid(row=2+9*(i//8),column=2+i%8)

        def display_buttons(self):
                if self.client_match.player_color==Color.BLACK:
                        first_row = 3
                        first_column = 9
                        step = -1
                else:
                        first_row = 10
                        first_column = 2
                        step = 1
                        
                for cb in self.cell_buttons:
                        r = cb.cell.position[0]
                        c = cb.cell.position[1]
                        rw = first_row-step*r
                        cn = first_column+step*c
                        cb.frame.grid(column=cn,row=rw)
                
        #$def new_match(self, match):
        def new_match(self,color=Color.NONE): #$
                print("Match_GUI.new_match")
                #$self.match = match
                #$self.client_match = client_match
                #$self.board = match.board
                if not color==Color.WHITE:
                        print("reversing")
                        #self.row_labels.reverse()
                        #self.column_labels.reverse()
                        self.display_labels()
                self.annotation_box.delete(1.0,tkinter.END)
                #$self.new_match_button.configure(command=self.match.new_match)
                self.new_match_button.configure(command=self.client_match.new_match) #$
                self.new_match_button.grid_forget()
                self.head_label["text"]="White Turn"
                #$rows = reversed(self.board.cells) if self.match.n_matches%2 else self.board.cells
                self.display_buttons()
                #rows = reversed(self.client_match.cells) if self.client_match.n_matches%2 else self.client_match.cells #$
                #for r in rows:
                #        #$columns = reversed(r) if  self.match.n_matches%2 else r
                #        columns = reversed(r) if  self.client_match.n_matches%2 else r #$
                #        for c in columns:
                #                self.cell_buttons[cb].cell = c
                #                cb += 1
                self.update_buttons(True)
                #$m,s = divmod(int(self.match.time_left[0]),60)
                m,s = divmod(int(self.client_match.player_time_left),60) #$
                time_string = f'{m:02d}:{s:02d}'
                self.top_timer_label["text"] = time_string
                self.bottom_timer_label["text"] = time_string

        def update_timer(self,time_left):
                if time_left>20:
                        m,s = divmod(int(time_left),60)
                        time_string = f'{m:02d}:{s:02d}'
                else:
                        time_string = str(time_left)
                if not self.client_match.game_started:
                        #print("hello")
                        self.top_timer_label["text"] = time_string
                        self.bottom_timer_label["text"] = time_string
                else:
                        timer_label = self.bottom_timer_label if self.client_match.player_turn else self.top_timer_label
                        timer_label["text"] = time_string
                #$if (white_up and self.match.is_white_turn) or ((not white_up) and (not self.match.is_white_turn)):
                #$        self.top_timer_label["text"]=time_string
                        #self.top_timer_label.grid(row=1,column=0)
                #$else:
                #$        self.bottom_timer_label["text"]=time_string
                        #self.bottom_timer_label.grid(row=12,column=0)
                
        def destroy(self):
                self.window.destroy()
                #del self.cell_buttons
                
        def execute_promotion_dialog(self):
                self.draw_button["state"] = "disabled"
                self.resign_button["state"] = "disabled"
                self.promotion_piece_type = tkinter.IntVar() 
                self.rbQ = tkinter.Radiobutton(self.window, text=chr(9813), variable=self.promotion_piece_type, value=1, command=self.choose_piece_type) 
                self.rbR = tkinter.Radiobutton(self.window, text=chr(9814), variable=self.promotion_piece_type, value=2, command=self.choose_piece_type) 
                self.rbB = tkinter.Radiobutton(self.window, text=chr(9815), variable=self.promotion_piece_type, value=3, command=self.choose_piece_type) 
                self.rbK = tkinter.Radiobutton(self.window, text=chr(9816), variable=self.promotion_piece_type, value=4, command=self.choose_piece_type)
                self.rbQ.grid(row=13,column=2,columnspan=2)
                self.rbR.grid(row=13,column=4,columnspan=2)
                self.rbB.grid(row=13,column=6,columnspan=2)
                self.rbK.grid(row=13,column=8,columnspan=2)
        def choose_piece_type(self):
                self.rbQ.grid_forget()
                self.rbR.grid_forget()
                self.rbB.grid_forget()
                self.rbK.grid_forget()
                t = self.promotion_piece_type.get()
                if t==1:
                        new_piece_type = Piece_type.QUEEN
                elif t==2:
                        new_piece_type = Piece_type.ROOK
                elif t==3:
                        new_piece_type = Piece_type.BISHOP
                else:
                        new_piece_type = Piece_type.KNIGHT
                        
                #$self.match.player.promote_pawn(self.pawn_promoted,new_piece_type)
                #$self.match.update_status()
                self.client_match.move(self.client_match.from_cell, self.client_match.to_cell, new_piece_type)
                self.promotion_dialog_on = False
                self.draw_button["state"] = "normal"
                self.resign_button["state"] = "normal"
                
        
        def move(self,from_cell,to_cell):
                self.clicked_button = None
                self.client_match.from_cell = from_cell.position
                self.client_match.to_cell = to_cell.position
                #self.client_match.from_cell[0] = from_cell.position[0]
                #self.client_match.from_cell[1] = from_cell.position[1]
                #self.client_match.to_cell[0] = to_cell.position[0]
                #self.client_match.to_cell[1] = to_cell.position[1]
                #$piece = from_cell.piece
                #$self.annotate_move(piece,to_cell)
                #$self.match.player.move_piece(piece,to_cell)
                #$self.update_buttons()
                #print(self.board.cells[to_cell.position[0]][to_cell.position[1]].piece.symbol + ' in ' + \
                
                #      self.board.cells[to_cell.position[0]][to_cell.position[1]].piece.current_cell.get_position() +
                #      ' button: ', self.cell_buttons[to_cell.position[0]*8+to_cell.position[1]].button.cget('text'))
                if from_cell.piece_type==Piece_type.PAWN and (to_cell.position[0]==0 or to_cell.position[0]==7):
                        self.promotion_dialog_on = True
                        #$self.pawn_promoted = piece
                        self.execute_promotion_dialog()
                else:
                        #$self.match.update_status()
                        print("Client_GUI.move calling Client_match.move",from_cell.position,to_cell.position) 
                        self.client_match.move(from_cell.position,to_cell.position)
                
        def update_status(self):
                game_over = False

                if not self.client_match.last_move_annotation is None:
                        self.annotation_box.insert(tkinter.END,self.client_match.last_move_annotation)
                        
                if self.client_match==Status.NEW_GAME:
                        print("hello")
                        self.new_match()
                elif self.client_match.status==Status.CHECKMATE:
                        player_text = "You" if self.client_match.player_turn else "Opponent"
                        self.head_label["text"] = player_text + " won - CHECKMATE!!!"
                        game_over = True
                elif self.client_match.status==Status.STALEMATE:
                        self.head_label["text"] = "Draw - Stalemate!"
                        game_over = True
                elif self.client_match.status==Status.REPEATED_MOVES:
                        self.head_label["text"] = "Draw - Repeated Moves"
                        game_over = True
                elif self.client_match.status==Status.PASSIVITY:
                        self.head_label["text"] = "Draw - 50 Move Rule"
                        game_over = True
                elif self.client_match.status==Status.NO_MATERIAL:
                        self.head_label["text"] = "Draw - not enough material"
                        game_over = True                        
                elif self.client_match.status==Status.TIME_UP:
                        if self.client_match.player_time_left and self.client_match.player_turn:
                                result_text = "You won on time!"
                        elif (not self.client_match.player_time_left) and (not self.client_match.player_turn):
                                result_text = "You lost on time!"
                        else:
                                result_text = "Draw - time up but no material"
                        self.head_label["text"] = result_text
                        game_over = True
                elif self.client_match.status==Status.RESIGNED:
                        player_text = "You" if not self.client_match.action==Action.RESIGN else "Opponent"
                        self.head_label["text"] = player_text + " won - Resignation"
                        game_over = True
                elif self.client_match.status==Status.DRAW_OFFERED:
                        if self.client_match.action==Action.OFFER:
                                self.draw_button["state"] = "disabled"                                        
                        else:
                                self.draw_button["text"] = "Accept draw?"
                else:
                        if self.draw_button["state"]=="disabled" or self.draw_button["text"]=="Accept draw?":
                                self.draw_button["state"] = "normal"
                                self.draw_button["text"] = "draw"                         
                        if self.client_match.status==Status.DRAW_AGREED:
                                self.head_label["text"] = "Draw - agreement"
                                game_over = True                      
                        

                if game_over:
                        self.new_match_button.grid(row=14,column=3,columnspan=6)
                else:
                        #if self.match.status==Status.NEW_GAME:
                                #print("Match_GUI.update_status, NEW_GAME")
                        if not self.client_match.game_started or not self.client_match.player_turn:
                                self.update_timer(self.client_match.opponent_time_left)
                        player_text = "Your " if self.client_match.player_turn else "Opponent "
                        turn_text = player_text + "turn"
                        self.head_label["text"] = turn_text
                self.update_buttons()
                                
                
        def update_buttons(self,new_match=False):
                for cb in self.cell_buttons:
                        cb.update(new_match)
                        #print(self.clicked_button,cb.cell.position,self.client_match.player_turn,cb.cell.color==self.client_match.player_color,not (cb.cell.piece_type==Piece_type.NONE),cb.cell.target_cells,end='  ')
                        
                        if self.clicked_button and cb is self.clicked_button:
                                cb.button["state"] = "normal"
                                cb.frame.config(bg=cb.clicked_color)
                        elif self.clicked_button and self.client_match.is_cell_in_target_cells(cb.cell.position, self.clicked_button.cell):
                                cb.button["state"] = "normal"
                                cb.frame.config(bg=cb.target_color)
                        elif self.client_match.player_turn and cb.cell.color==self.client_match.player_color and (not cb is self.clicked_button) and cb.cell.target_cells:
                                cb.button["state"] = "normal"
                                cb.frame.config(bg=cb.available_color)
                        else:
                                cb.button["state"] = "disabled"
                                cb.frame.config(bg=cb.cell_color)
                        
